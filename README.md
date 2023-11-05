# Ubuntu Summit 2023 - Charmed Spark

This repository contains the material of the Demo held at Ubuntu Summit 2023 for Charmed Spark.

## Playscript

The demo is broken into 4 stages:
1. Setup
2. Develop
3. Integration with other applications: Charmed Kafka
4. Monitor
 

##### Prerequisite

* Ubuntu 22.04

#### Setup

To carry out this demo, we will need a few components that needs to be installed.

###### MicroK8s

```shell
sudo snap install microk8s --channel=1.28-strict/stable
sudo microk8s enable hostpath-storage dns rbac storage minio
IPADDR=$(ip -4 -j route get 2.2.2.2 | jq -r '.[] | .prefsrc')
sudo microk8s enable metallb:$IPADDR-$IPADDR
sudo snap alias microk8s.kubectl kubectl 
mkdir -p ~/.kube
sudo usermod -a -G snap_microk8s ubuntu
sudo chown -R ubuntu ~/.kube
newgrp snap_microk8s
microk8s config > ~/.kube/config
```

MicroK8s will be used for deploying Spark workload locally.


###### docker

```shell
sudo snap install docker
sudo addgroup --system docker
sudo adduser $USER docker
sudo snap disable docker
sudo snap enable docker
```

Docker will be used to access the Jupyter notebook.


###### Juju CLI 

```shell
sudo snap install juju --channel 3.1/stable
```

The Juju CLI will be used for interacting with the Juju controller
for managing services via charmed operators.



###### `spark-client`

```shell
sudo snap install spark-client --channel 3.4/edge
```

The `spark-client` Snap provides a number of utilities to manage Spark service accounts as well 
starting Spark job on a K8s cluster. 

##### Resources

Once all the components are installed, we then need to set up a S3 bucket and copy the relevant data inside the bucket.

To make sure that MinIO is up and running, you can run the script:

```shell
./bin/check-minio.sh
```

That should output that the service is up and running and provide you with the endpoints and the credentials (access key and access secret).

You can also access to the MinIO Web UI by fetching the IP of the service related to the UI:

```shell
MINIO_UI_IP=$(kubectl get svc microk8s-console -n minio-operator -o yaml | yq .spec.clusterIP)
```


The data from this repository. e.g.`data` and `script`, that will be used in this demo.

In order to do so, you can use the Python scripts bundled in this repository for creating and 
setting up (e.g. copying the files needed for the demo) the S3 bucket

```shell
python scripts/spark_bucket.py \
  --action create setup \
  --access-key $ACCESS_KEY \
  --secret-key $SECRET_KEY \
  --endpoint $S3_ENDPOINT \
  --bucket $S3_BUCKET 
```


You can now create the Spark service account on the K8s cluster that will be used to run the 
Spark workloads. The services will be created via the `spark-client.service-account-registry`
as `spark-client` will provide enhanced features to run your Spark jobs seamlessly integrated 
with the other parts of the Charmed Spark solution. 

For instance, `spark-client` allows you to bind your service account a hierarchical set of 
configurations that will be used when submitting Spark jobs. 

For instance, in this demo we will use S3 bucket to fetch and store data. 

Spark settings are specified in a 
[configuration file](./confs/s3.conf) and can be fed into the service account creation command
 (that also handles the parsing of environment variables specified in the configuration file), e.g. 

```shell
kubectl create namespace spark
spark-client.service-account-registry create \
  --username spark --namespace spark \
  --properties-file ./confs/s3.conf
```

You can find more information about the hierarchical set of configurations 
[here](https://discourse.charmhub.io/t/spark-client-snap-explanation-hierarchical-configuration-handling/8956) 
and how to manage Spark service account via `spark-client` 
[here](https://discourse.charmhub.io/t/spark-client-snap-tutorial-manage-spark-service-accounts/8952)

That's it! You are now ready to use Spark!

#### Develop

Charmed Spark offers several ways to interact with a Spark cluster: 
- Jupyter notebook integrated in the Charmed Spark Rock image
- Submit jobs with the `spark-client-snap`
- Interact with the Pyspark shell or Scala shell

##### Interact with Spark on a Jupyter notebook

It is always very convenient when you are either exploring some data or doing some first development
to use Jupyter notebook, assisted with a user-friendly and interactive environment where you can 
mix python (together with plots) and markdown code.

To start a Jupyter notebook server that provides a binding to Spark already integrated in 
your notebooks, you can run the Charmed Spark OCI image

```shell
docker run --name charmed-spark --rm \
  -v $HOME/.kube/config:/var/lib/spark/.kube/config \
  -v $(pwd):/var/lib/spark/notebook/repo \
  -p 8080:8888 \
  ghcr.io/canonical/charmed-spark:3.4-22.04_edge \
  \; start jupyter 
```

It is important for the image to have access to the Kubeconfig file (in order to fetch the 
Spark configuration via the `spark-client` CLI) as well as the local notebooks directory to access 
to the notebook already provided. 

When the image is up and running, you can navigate with your browser to

```shell
http://<IP_ADDRESS>:8080
```

You can now either start a new notebook or use the one provided in `./notebooks/Demo.ipynb`.
As you start a new notebook, you will already have a `SparkContext` and a `SparkSession` object 
defined by two variables, `sc` and `spark` respectively,

```python
> sc
SparkContext

Spark UI

Version           v3.4.1
Master            k8s://https://192.168.1.4:16443
AppName           PySparkShell
```

In fact, the notebook (running locally on Docker) acts as driver, and it spawns executor pods on 
Kubernetes. This can be confirmed by running

```shell
kubectl get pod -n spark
```

which should output something like

```shell
NAME                                                        READY   STATUS      RESTARTS   AGE
pysparkshell-79b4df8ad74ab7da-exec-1                        1/1     Running     0          5m31s
pysparkshell-79b4df8ad74ab7da-exec-2                        1/1     Running     0          5m29s
```

##### Spark Submit

Beside running Jupyter notebooks, the `spark-client` SNAP also allow you to submit Python 
scripts/job. In this case, we recommend you to run both driver and executor in kubernetes. 
Therefore, the python program needs to be uploaded to a location that can be reached by the pods, 
such that it can be downloaded by the driver to be executed. 

The setup of the S3 bucket above should have already uploaded the data and the script to 
`data/data.csv.gz` and `scripts/stock_country_report.py` respectively.

Therefore, you should be able to run

```shell
spark-client.spark-submit \
  --username spark --namespace spark \
  --deploy-mode cluster \
  s3a://$S3_BUCKET/scripts/stock_country_report.py \
    --input  s3a://$S3_BUCKET/data/data.csv.gz \
    --output s3a://$S3_BUCKET/data/output_report_microk8s
```

##### Access Spark from shell

Last but not least, the `spark-client` SNAP offers the possibily to open an interactive shell in which a user can type and shell the results of their computation. 


```shell
spark-client.spark-shell \
  --username spark --namespace spark
```

Now we can start typing commands in an interactive way.

```scala
import scala.math.random
val slices = 100
val n = math.min(100000L * slices, Int.MaxValue).toInt
val count = spark.sparkContext.parallelize(1 until n, slices).map { i => val x = random * 2 - 1; val y = random * 2 - 1;  if (x*x + y*y <= 1) 1 else 0;}.reduce(_ + _)
println(s"Pi is roughly ${4.0 * count / (n - 1)}")

```

#### Integrate Charmed Spark with Charmed Kafka 

First create a fresh Juju model to be used as a workspace for spark-streaming experiments.

```shell
juju add-model spark-streaming
```

Deploy the Zookeeper and the Kafka k8s-charms. Single units should be enough. 

```shell
juju deploy zookeeper-k8s --series=jammy --channel=edge

juju deploy kafka-k8s --series=jammy --channel=edge

juju relate  kafka-k8s  zookeeper-k8s
```

Deploy a test producer application, to write messages to Kafka.

```shell
juju deploy kafka-test-app --series=jammy --channel=edge --config role=producer --config topic_name=spark-streaming-store --config num_messages=1000

juju relate kafka-test-app  kafka-k8s
```

In order to consume these messages, credentials are required to establish a connection between Spark and Kafka.

We need to setup the Juju data-integrator module, which perform credential retrieval as shown below.

```shell
juju deploy data-integrator --series=jammy --channel=edge --config extra-user-roles=consumer,admin --config topic-name=spark-streaming-store

juju relate data-integrator kafka-k8s 

juju run-action data-integrator/0 get-credentials --wait 
```

Now we can get credentials for the data-integrator:

```shell
USERNAME=$(juju run data-integrator/0 get-credentials --format=json | yq .data-integrator/0.results.kafka.username)
PASSWORD=$(juju run data-integrator/0 get-credentials --format=json | yq .data-integrator/0.results.kafka.password)
```

Now we can setup service account in this namespace: 

```shell
spark-client.service-account-registry create \
  --username spark --namespace spark-streaming \
  --properties-file ./confs/s3.conf
```

and submit the job that uses Spark streaming apis:


```shell
spark-client.spark-submit \
  --username spark --namespace spark-streaming \
  --deploy-mode cluster \
  --conf spark.executor.instances=1 \
  --conf spark.jars.ivy=/tmp \
  --packages org.apache.spark:spark-streaming-kafka-0-10_2.12:3.4.1,org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.1 \
  s3a://$S3_BUCKET/scripts/streaming_example.py \
    --kafka-username  $USERNAME \
    --kafka-password $PASSWORD

```

The `streaming_example.py` script looks like the following:

```python
import argparse
from pyspark.sql import SparkSession
from pyspark.sql.functions import udf, col
from json import loads

spark = SparkSession.builder.getOrCreate()

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("--username", "-u",
                  help="The username to authenticate to Kafka",
                  required=True)
  parser.add_argument("--password", "-p",
                  help="The password to authenticate to Kafka",
                    required=True)

  args = parser.parse_args()
  username=args.username
  password=args.password
  lines = spark.readStream \
          .format("kafka") \
          .option("kafka.bootstrap.servers", "kafka-k8s-0.kafka-k8s-endpoints:9092") \
          .option("kafka.sasl.mechanism", "SCRAM-SHA-512") \
          .option("kafka.security.protocol", "SASL_PLAINTEXT") \
          .option("kafka.sasl.jaas.config", f'org.apache.kafka.common.security.scram.ScramLoginModule required username="{username} password={password};') \
          .option("subscribe", "spark-streaming-store") \
          .option("includeHeaders", "true") \
          .load()

  get_origin = udf(lambda x: loads(x)["origin"])
  w_count = lines.withColumn("origin", get_origin(col("value"))).select("origin").groupBy("origin").count()


  query = w_count \
    .writeStream \
    .outputMode("complete") \
    .format("console") \
    .start()

query.awaitTermination()
```

### Monitor

Logs of driver and executors are by default stored on the pod local file system, and are therefore
lost once the jobs finishes. However, Spark allows us to store these logs into S3, such that 
they can be re-read and visualized by the Spark History Server, allowing to monitor and visualise
the information and metrics about the job execution. 

To enable monitoring, we should therefore
* Configure the Spark service account to provide configuration for Spark jobs to store logs in 
   a S3 bucket
* Deploy the Spark History Server with Juju, configuring it to read from the same bucket

#### Spark service account configuration 

The configuration needed for storing logs on the S3 bucket can be appended to the already 
existing ones with the following command

```shell
spark-client.service-account-registry add-config \
  --username spark --namespace spark \
  --properties-file ./confs/spark-monitoring.conf
```

#### Deploy Spark History Server with Juju

First of all, you need to register the K8s cluster in Juju with

```shell
juju add-k8s spark-cluster
```

You then need to bootstrap a Juju controller responsible for managing your services

```shell
juju bootstrap spark-cluster
```

##### Deploy the charms

First, add a new model/namespace where to deploy the History Server related charms

```shell
juju add-model history-server
```

You can now deploy all the charms required by the History Server, using the provided bundle 
(but replacing the environment variable)

```shell

juju deploy spark-history-server-k8s -n1 --channel 3.4/stable
juju deploy s3-integrator -n1 --channel edge
juju config s3-integrator bucket=$S3_BUCKET path="spark-events" endpoint=$S3_ENDPOINT

```

###### S3 Integrator 

the `s3-integrator` needs to be correctly configured by providing the S3 credentials, e.g. 

```shell
juju run s3-integrator/leader sync-s3-credentials \
  access-key=$ACCESS_KEY secret-key=$SECRET_KEY
```

After the setup of the keys we can now relate the two charms.

```
juju relate s3-integrator spark-history-server-k8s
```

Apply the configuration settings needed to enable the Spark history server:

```shell
spark-client.service-account-registry add-config \
  --username spark --namespace spark \
  --properties-file ./confs/spark-history-server.conf
```


Run a sample jobs and now you can check the logs in the history-server at the port 18080.


#### Monitor Spark with the Observability framework


##### Enable Monitoring

The Charmed Spark solution comes with the [spark-metrics](https://github.com/banzaicloud/spark-metrics) exporter embedded in the [Charmed Spark OCI image](https://github.com/canonical/charmed-spark-rock), used as base for driver and executors pods .
This exporter is designed to push metrics to the [prometheus pushgateway](https://github.com/prometheus/pushgateway), that is integrated with the [Canonical Observability Stack](https://charmhub.io/topics/canonical-observability-stack). 


In order to enable the observability on Charmed Spark two steps are necessary:

1. Setup the Observability bundle with juju
2. Configure the Spark service account


##### Setup the Observability bundle with Juju

As a prerequisite, you need to have Juju 3 installed with a MicroK8s controller bootstrapped. This can be done following this [tutorial](https://charmhub.io/topics/canonical-observability-stack/tutorials/install-microk8s).


As a first step, start by deploying cos-lite bundle in a Kubernetes environment with Juju.

```shell
juju add-model cos
juju switch cos
juju deploy cos-lite --trust
```
Some extra charms are needed to integrate the Charmed Spark with the Observability bundle. This includes the `prometheus-pushgateway-k8s` charm and the `cos-configuration-k8s grafana` that is used to configure the Grafana dashboard. We provide a basic dashboard [here](https://github.com/canonical/charmed-spark-rock/blob/dashboard/dashboards/prod/grafana/spark_dashboard.json).

```shell
juju deploy prometheus-pushgateway-k8s --channel edge
# deploy cos configuration charm to import the grafana dashboard
juju deploy cos-configuration-k8s \
  --config git_repo=https://github.com/canonical/charmed-spark-rock \
  --config git_branch=dashboard \
  --config git_depth=1 \
  --config grafana_dashboards_path=dashboards/prod/grafana/
# relate cos-configration charm to import grafana dashboard
juju relate cos-configuration-k8s grafana
juju relate prometheus-pushgateway-k8s prometheus

```

This allows to configure a custom scraping interval that prometheus will used to retrieve the exposed metrics.


Eventually, you will need to retrive the credentials for logging into the Grafana dashboard, by using the following action:
``` shell
juju run grafana/leader get-admin-password
```

Get address of the prometheus pushgateway.

```shell
export PROMETHEUS_GATEWAY=$(juju status --format=yaml | yq ".applications.prometheus-pushgateway-k8s.address") 
export PROMETHEUS_PORT=9091
```

To enable the push of metrics you only need to add the following lines as configuration to a `spark-client` configuration file (e.g., `spark-monitoring.conf`): 

```shell
spark.metrics.conf.driver.sink.prometheus.pushgateway-address=<PROMETHEUS_GATEWAY_ADDRESS>:<PROMETHEUS_PORT>
spark.metrics.conf.driver.sink.prometheus.class=org.apache.spark.banzaicloud.metrics.sink.PrometheusSink
spark.metrics.conf.driver.sink.prometheus.enable-dropwizard-collector=true
spark.metrics.conf.driver.sink.prometheus.period=5
spark.metrics.conf.driver.sink.prometheus.metrics-name-capture-regex=([a-z0-9]*_[a-z0-9]*_[a-z0-9]*_)(.+)
spark.metrics.conf.driver.sink.prometheus.metrics-name-replacement=\$2
spark.metrics.conf.executor.sink.prometheus.pushgateway-address=<PROMETHEUS_GATEWAY_ADDRESS>:<PROMETHEUS_PORT>
spark.metrics.conf.executor.sink.prometheus.class=org.apache.spark.banzaicloud.metrics.sink.PrometheusSink
spark.metrics.conf.executor.sink.prometheus.enable-dropwizard-collector=true
spark.metrics.conf.executor.sink.prometheus.period=5
spark.metrics.conf.executor.sink.prometheus.metrics-name-capture-regex=([a-z0-9]*_[a-z0-9]*_[a-z0-9]*_)(.+)
spark.metrics.conf.executor.sink.prometheus.metrics-name-replacement=\$2
```



### Scale

Running Charmed Spark on Microk8s is bounded to your local envinroment resources. To do so it will be possible to run Charmed Spark on AWS EKS. We don't have time to tackle this on this demo but we have a nice demostration running at the [2023 Operator Day](https://github.com/deusebio/operator-day-2023-charmed-spark).



### Cleanup

First destroy the Juju model and controller

```shell
juju destroy-controller --force --no-wait \
  --destroy-all-models \
  --destroy-storage spark-cluster
```


Finally, you can also remove the S3-bucket that was used during the demo via the provided Python
script

```shell
python scripts/spark_bucket.py \
  --action delete \
  --access-key $AWS_ACCESS_KEY \
  --secret-key $AWS_SECRET_KEY \
  --endpoint $AWS_S3_ENDPOINT \
  --bucket $AWS_S3_BUCKET 
```
