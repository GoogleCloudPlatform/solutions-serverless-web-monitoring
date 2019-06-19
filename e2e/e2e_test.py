# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import backoff
import json
import pytest

from googleapiclient.discovery import build
import google.auth
from google.cloud import firestore
from google.cloud import pubsub_v1
from google.cloud import storage


# supplied as arguments to the test
PROJECT = None
REGION = None
METRICS_BUCKET = None
TRACER_FUNCTION = None
ALERT_SUBSCRIPTION = None


# [START main-tests-block]
def test_e2e_pass():
  run_pipeline('http://www.example.com/', True)


def test_e2e_fail():
  run_pipeline('https://cloud.google.com/docs/tutorials', False)


def run_pipeline(url, should_pass):
  """Triggers the web analysis pipeline and verifies outputs of each stage.

  Args:
    url (str): The page to analyze.
    should_pass (bool): Whether the page should load within the threshold time.
  """
  trace_response = call_tracer(url)
  filename = assert_tracer_response(trace_response)
  assert_gcs_objects(filename)
  assert_firestore_doc(filename, should_pass)
  assert_pubsub_message(should_pass)

  # clean up
  delete_gcs_objects(filename)
  delete_firestore_doc(filename)
# [END main-tests-block]


# [START call-tracer-block]
@backoff.on_predicate(backoff.constant, lambda resp: 'error' in resp,
                      max_tries=3, interval=5)
def call_tracer(url):
  credentials, project = google.auth.default()
  service = build('cloudfunctions', 'v1', credentials=credentials)
  function_url = 'projects/{}/locations/{}/functions/{}'.format(
      PROJECT, REGION, TRACER_FUNCTION)
  post_data_str = json.dumps({'url': url})
  body = {'data': post_data_str}
  request = service.projects().locations().functions().call(
      name=function_url, body=body)
  return request.execute()
# [END call-tracer-block]


def assert_tracer_response(response):
  assert 'error' not in response
  assert 'result' in response
  result_obj = json.loads(response['result'])
  assert 'filename' in result_obj
  filename = result_obj['filename']
  return filename


def assert_gcs_objects(filename):
  gcs = storage.Client()
  bucket = gcs.get_bucket(METRICS_BUCKET)
  assert bucket.blob(filename).exists()


def delete_gcs_objects(filename):
  gcs = storage.Client()
  bucket = gcs.get_bucket(METRICS_BUCKET)
  bucket.blob(filename).delete()


def assert_firestore_doc(filename, should_pass):
  db = firestore.Client(project=PROJECT)
  coll_ref = db.collection('page-metrics')
  doc = get_doc(coll_ref, filename)

  assert doc is not None
  values = doc.to_dict()
  assert 'metrics' in values
  assert values is not None
  if should_pass:
    assert 'PASS' in values['status']
  else:
    assert 'FAIL' in values['status']


@backoff.on_predicate(backoff.constant, max_time=15, interval=5)
def get_doc(collection, doc_id):
  """Retrieve a Firestore doc, with retries to allow Function time to trigger"""
  doc = collection.document(doc_id).get()
  if doc.exists:
    return doc


def delete_firestore_doc(filename):
  db = firestore.Client(project=PROJECT)
  doc_ref = db.collection('page-metrics').document(filename)
  doc_ref.delete()


def assert_pubsub_message(should_pass):
  subscriber = pubsub_v1.SubscriberClient()
  subscription = subscriber.subscription_path(PROJECT, ALERT_SUBSCRIPTION)
  received_messages = get_messages(subscriber, subscription)

  # expect zero alert messages if successful
  if should_pass:
    assert not received_messages
  else:
    assert len(received_messages) >= 1
    rec_message = received_messages[0]
    data = rec_message.message.data
    assert data is not None
    jsonobj = json.loads(data.decode())
    assert jsonobj['fields']['status']['stringValue'] == 'FAIL'
    subscriber.acknowledge(subscription, [rec_message.ack_id])


@backoff.on_predicate(backoff.constant, max_time=15, interval=5)
def get_messages(subscriber, subscription):
  """Retrieve PubSub messages, with retries to allow Function time to trigger"""
  response = subscriber.pull(subscription, max_messages=1,
                             return_immediately=True)
  assert response is not None
  return response.received_messages


# [START setup-block]
@pytest.fixture(autouse=True, scope='module')
def setup(pytestconfig):
  global PROJECT, REGION, METRICS_BUCKET, TRACER_FUNCTION, ALERT_SUBSCRIPTION

  # if we used Terraform to create the GCP resources, use the output variables
  if pytestconfig.getoption('tfstate') is not None:
    tf_state_file = pytestconfig.getoption('tfstate')
    with open(tf_state_file, 'r', encoding='utf-8') as fp:
      tf_state = json.load(fp)
      tf_output_vars = tf_state['outputs']
      PROJECT = tf_output_vars['project']['value']
      REGION = tf_output_vars['region']['value']
      METRICS_BUCKET = tf_output_vars['bucket_metrics']['value']
      TRACER_FUNCTION = tf_output_vars['function_tracer']['value']
      ALERT_SUBSCRIPTION = tf_output_vars['pubsub_subscription_alerts']['value']

  #  otherwise variable passed directly on command line
  else:
    PROJECT = pytestconfig.getoption('project')
    REGION = pytestconfig.getoption('region')
    METRICS_BUCKET = pytestconfig.getoption('bucket_metrics')
    TRACER_FUNCTION = pytestconfig.getoption('function_tracer')
    ALERT_SUBSCRIPTION = pytestconfig.getoption('pubsub_subscription_alerts')

  assert PROJECT is not None
  assert REGION is not None
  assert METRICS_BUCKET is not None
  assert TRACER_FUNCTION is not None
  assert ALERT_SUBSCRIPTION is not None
# [END setup-block]
