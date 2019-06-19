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


def pytest_addoption(parser):
  # if Terraform was used to deploy resources, pass the state details
  parser.addoption("--tfstate", action="store", default=None)

  # otherwise pass values explicitly
  parser.addoption("--project", action="store", default=None)
  parser.addoption("--region", action="store", default=None)
  parser.addoption("--bucket_metrics", action="store", default=None)
  parser.addoption("--function_tracer", action="store", default=None)
  parser.addoption("--pubsub_subscription_alerts", action="store", default=None)

