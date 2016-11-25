import boto3
import gevent
import json
import random
from elasticsearch import Elasticsearch, exceptions, RequestsHttpConnection
import requests
from requests_aws4auth import AWS4Auth

WORKERS = 10
API_URL = "http://gateway-a.watsonplatform.net/calls/text/TextGetTextSentiment"
API_TOKEN = "0ac5fb44df7c0b67834d33197cb4117472020536"
QUEUE_NAME = "tweetsQueue"
WAIT_TIME = 10 # time to wait between each SQS poll
TOPIC_NAME = "tweet-topic"
SNS_ARN = "arn:aws:sns:us-east-1:648564116187:tweet-topic"
aws_access_key_id="AKIAIXLMABEUDHWWG2KA"
aws_secret_access_key="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"
REGION = "us-east-1"

awsauth = AWS4Auth(aws_access_key_id, aws_secret_access_key, REGION, 'es')
sqs = boto3.resource('sqs')
queue = sqs.get_queue_by_name(QueueName=QUEUE_NAME)
sns = boto3.client('sns')

es = Elasticsearch(
                   hosts=[{'host': 'search-tweet-qtio2avcrkgm4l6svwa2kfu3b4.us-east-1.es.amazonaws.com', 'port': 443}],
                   use_ssl=True,
                   http_auth=awsauth,
                   verify_certs=True,
                   connection_class=RequestsHttpConnection
                   )

def task(pid):
    print ("[Task " + str(pid) + "] Starting ...")
    while True:
        for message in queue.receive_messages():
            tweet = json.loads(message.body)
            payload = {
                'apikey': API_TOKEN, "outputMode": "json", "text": tweet["text"]
            }
            r = requests.get(API_URL, params=payload)
            if r.status_code == 200 and r.json().get("status") != "ERROR":
                tweet["sentiment"] = r.json().get("docSentiment")
                # index tweet in ES
                res = es.index(index="tweets", doc_type="tweet", id=tweet["id"], body=tweet)
                
                # send notification
                sns.publish(
                            TopicArn=SNS_ARN,
                            Message=json.dumps(tweet),
                            Subject='New Tweet')
                            
                print ("[Task " + str(pid) + ", tweetid " + str(tweet["id"]) + " indexed")
            message.delete()
        gevent.sleep(WAIT_TIME)


if __name__ == "__main__":
    threads = [gevent.spawn(task, pid) for pid in range(1, WORKERS+1)]
    gevent.joinall(threads)