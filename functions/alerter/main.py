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

import json
import logging
import os

from google.cloud import pubsub

publish_client = None


def generate_alert(data, context):
  """Cloud Function entry point, triggered by a change to a Firestore document.

  If the triggering document indicates a Failed status, send the document to
  configured PubSub topic.

  Args:
    data (dict): The event payload.
    context (google.cloud.functions.Context): Metadata for the event.
  """
  doc_fields = data['value']['fields']
  status = doc_fields['status']['stringValue']
  if 'FAIL' in status:
    global publish_client
    if not publish_client:
      publish_client = pubsub.PublisherClient()

    logging.info('Sending alert in response to %s status in document %s',
                 status, context.resource)
    project = os.environ.get('GCP_PROJECT')
    topic = os.environ.get('ALERT_TOPIC')
    fqtn = 'projects/{}/topics/{}'.format(project, topic)
    msg = json.dumps(data['value']).encode('utf-8')
    publish_client.publish(fqtn, msg)
