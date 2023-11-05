import argparse
from pyspark.sql import SparkSession
from pyspark.sql.functions import udf, col
from json import loads

spark = SparkSession.builder.getOrCreate()

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("--kafka-username", "-u",
                  help="The username to authenticate to Kafka",
                  required=True)
  parser.add_argument("--kafka-password", "-p",
                  help="The password to authenticate to Kafka",
                    required=True)

  args = parser.parse_args()
  username=args.kafka_username
  password=args.kafka_password
  lines = spark.readStream \
          .format("kafka") \
          .option("kafka.bootstrap.servers", "kafka-k8s-0.kafka-k8s-endpoints:9092") \
          .option("kafka.sasl.mechanism", "SCRAM-SHA-512") \
          .option("kafka.security.protocol", "SASL_PLAINTEXT") \
          .option("kafka.sasl.jaas.config", f'org.apache.kafka.common.security.scram.ScramLoginModule required username="{username}" password="{password}";') \
          .option("subscribe", "spark-streaming-store") \
          .option("includeHeaders", "true") \
          .load()

  get_origin = udf(lambda x: loads(x)["origin"])
  w_count = lines.withColumn("origin", get_origin(col("value"))).select("origin")\
          .groupBy("origin")\
          .count()
  query = w_count \
    .writeStream \
    .outputMode("complete") \
    .format("console") \
    .start()

  query.awaitTermination()
