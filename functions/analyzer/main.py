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

from datetime import datetime
import json
import logging
import os

from google.cloud import firestore
from google.cloud import storage

# API clients
gcs = None
db = None


def analyze(data, context):
  """Function entry point, triggered by creation of an object in a GCS bucket.

  The function reads the content of the triggering file, analyses its contents,
  and persists the results of the analysis to a new Firestore document.

  Args:
    data (dict): The trigger event payload.
    context (google.cloud.functions.Context): Metadata for the event.
  """
  page_metrics = get_gcs_file_contents(data)
  max_time_meaningful_paint = int(os.environ.get('MAX_TIME_MEANINGFUL_PAINT'))
  analysis_result = analyze_metrics(data, page_metrics,
                                    max_time_meaningful_paint)
  docref = persist(analysis_result, data['name'])
  logging.info('Created new Firestore document %s/%s describing analysis of %s',
               docref.parent.id, docref.id, analysis_result['input_file'])


def get_gcs_file_contents(data):
  """Get the content of the GCS object that triggered this function."""
  global gcs
  if not gcs:
    gcs = storage.Client()
  bucket = gcs.get_bucket(data['bucket'])
  blob = bucket.blob(data['name'])
  return blob.download_as_string()


def persist(analysis_result, document_id):
  """Persist analysis results to the configured Firestore collection."""
  global db
  if not db:
    db = firestore.Client()
  collection_name = os.environ.get('METRICS_COLLECTION')
  collection = db.collection(collection_name)
  inserted = collection.add(analysis_result, document_id=document_id)
  return inserted[1]


# [START parse-block]
def analyze_metrics(data, metrics, max_time_meaningful_paint):
  """Parse the page metrics and return a dict with details of the operation."""
  calculated = parse_metrics(metrics)
  gcs_filename = 'gs://{}/{}'.format(data['bucket'], data['name'])
  parse_result = {
      'metrics': calculated,
      'input_file': gcs_filename,
      'page_url': data['metadata']['pageUrl'],
      'fetch_timestamp': data['timeCreated'],
      'analysis_timestamp': datetime.utcnow().isoformat() + 'Z'
  }

  # check whether page performance is within threshold
  time_meaningful_paint = calculated['FirstMeaningfulPaint']
  if time_meaningful_paint > max_time_meaningful_paint:
    logging.warning('FAILED: page load time (%d) exceeded max threshold (%d)',
                    time_meaningful_paint, max_time_meaningful_paint)
    parse_result['status'] = 'FAIL'
  else:
    parse_result['status'] = 'PASS'
  return parse_result


def parse_metrics(metrics_str):
  metrics_obj = json.loads(metrics_str)
  metrics = metrics_obj['metrics']
  keys = [x['name'] for x in metrics]
  values = [x['value'] for x in metrics]
  kv = dict(zip(keys, values))
  calculated = {
      'DomContentLoaded': calc_event_time(kv, 'DomContentLoaded'),
      'FirstMeaningfulPaint': calc_event_time(kv, 'FirstMeaningfulPaint'),
      'JSHeapTotalSize': kv['JSHeapTotalSize'],
      'JSHeapUsedSize': kv['JSHeapUsedSize']
  }
  return calculated
# [END parse-block]


def calc_event_time(metrics_kv, event_name):
  return int((metrics_kv[event_name] - metrics_kv['NavigationStart']) * 1000)
