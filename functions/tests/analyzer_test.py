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

from functions.analyzer import main
import os
import pytest


trigger_data = {
  'bucket': 'gcsBucket',
  'name': 'gcsObjectName',
  'timeCreated': '2019-03-07 00:00:00Z',
  'metadata': {
    'pageUrl': 'https://www.testtest.com'
  }
}

METRICS_FILE = os.path.join(os.path.dirname(__file__),
                            'sample-metrics.json')


@pytest.fixture()
def input_file():
  with open(METRICS_FILE) as json_file:
    return json_file.read()


@pytest.mark.parametrize('max_time, expected_status',
                         [(2000, 'PASS'), (500, 'FAIL')])
def test_analyze_metrics(input_file, max_time, expected_status):
  result = main.analyze_metrics(trigger_data, input_file, max_time)
  assert result is not None
  assert result['status'] == expected_status
  assert result['input_file'] == 'gs://gcsBucket/gcsObjectName'
  assert result['fetch_timestamp'] == '2019-03-07 00:00:00Z'
  assert 'metrics' in result
  assert_metrics(result['metrics'])


def test_parse_metrics(input_file):
  parsed = main.parse_metrics(input_file)
  assert_metrics(parsed)


def assert_metrics(parsed):
  assert parsed is not None
  assert len(parsed) == 4
  assert 'DomContentLoaded' in parsed
  assert 'FirstMeaningfulPaint' in parsed
  assert 'JSHeapTotalSize' in parsed
  assert 'JSHeapUsedSize' in parsed
  assert parsed['FirstMeaningfulPaint'] == 786
