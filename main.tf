/**
 * Copyright 2019 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

terraform {
  required_version = ">= 0.12.0"
}

// [START variables-block]
variable "project_id" {}
variable "region" {}
variable "suffix" {}
variable "fscollection_analysis" {
  default = "page-metrics"
}
variable "allowed_hosts" {
  default = "www\\.example\\.com|cloud\\.google\\.com"
}
variable "max_time_to_meaningful_paint" {
  default = 3000
}
variable "local_output_path" {
  default = "build"
}
// [END variables-block]


provider "google" {
  project = "${var.project_id}"
  region = "${var.region}"
  version = "2.15.0"
}

provider "archive" {}


// [START gcs-buckets-block]
resource "google_storage_bucket" "bucket_metrics" {
  name = "page-metrics-${var.suffix}"
  storage_class = "REGIONAL"
  location  = "${var.region}"
  force_destroy = "true"
}

resource "google_storage_bucket" "bucket_source_archives" {
  name = "gcf-source-archives-${var.suffix}"
  storage_class = "REGIONAL"
  location  = "${var.region}"
  force_destroy = "true"
}
// [END gcs-buckets-block]


// [START pubsub-block]
resource "google_pubsub_topic" "topic_alerts" {
  name = "performance-alerts-${var.suffix}"
}

resource "google_pubsub_subscription" "subscription_alerts" {
  name = "performance-alerts-sub-${var.suffix}"
  topic = "${google_pubsub_topic.topic_alerts.name}"
}
// [END pubsub-block]


// [START all-functions-block]
/**
 * Cloud Functions.
 * For each function, zip up the source and upload to GCS.
 * Uploaded source is referenced in the Function deploy.
 */

// [START function-tracer-block]
data "archive_file" "local_tracer_source" {
  type        = "zip"
  source_dir  = "./functions/tracer"
  output_path = "${var.local_output_path}/tracer.zip"
}

resource "google_storage_bucket_object" "gcs_tracer_source" {
  name   = "tracer.zip"
  bucket = "${google_storage_bucket.bucket_source_archives.name}"
  source = "${data.archive_file.local_tracer_source.output_path}"
}

resource "google_cloudfunctions_function" "function_tracer" {
  name = "tracer-${var.suffix}"
  project = "${var.project_id}"
  region = "${var.region}"
  available_memory_mb = "1024"
  entry_point = "trace"
  runtime = "nodejs8"
  trigger_http = "true"
  source_archive_bucket = "${google_storage_bucket.bucket_source_archives.name}"
  source_archive_object = "${google_storage_bucket_object.gcs_tracer_source.name}"
  environment_variables = {
    BUCKET_METRICS = "${google_storage_bucket.bucket_metrics.name}"
    ALLOWED_HOSTS = "${var.allowed_hosts}"
  }
}

// prevent unauthenticated invocations
resource "google_cloudfunctions_function_iam_binding" "tracer_disallow_unauthenticated" {
  project = "${var.project_id}"
  region = "${var.region}"
  cloud_function = "${google_cloudfunctions_function.function_tracer.name}"
  role = "roles/cloudfunctions.invoker"
  members = [
  ]
  depends_on = [
    google_cloudfunctions_function.function_tracer
  ]
}
// [END function-tracer-block]


// [START function-analyzer-block]
data "archive_file" "local_analyzer_source" {
  type        = "zip"
  source_dir  = "./functions/analyzer"
  output_path = "${var.local_output_path}/analyzer.zip"
}

resource "google_storage_bucket_object" "gcs_analyzer_source" {
  name   = "analyzer.zip"
  bucket = "${google_storage_bucket.bucket_source_archives.name}"
  source = "${data.archive_file.local_analyzer_source.output_path}"
}

resource "google_cloudfunctions_function" "function_analyzer" {
  name = "analyzer-${var.suffix}"
  project = "${var.project_id}"
  region = "${var.region}"
  available_memory_mb = "256"
  entry_point = "analyze"
  runtime = "python37"
  source_archive_bucket = "${google_storage_bucket.bucket_source_archives.name}"
  source_archive_object = "${google_storage_bucket_object.gcs_analyzer_source.name}"
  event_trigger {
    event_type = "google.storage.object.finalize"
    resource = "${google_storage_bucket.bucket_metrics.name}"
  }
  environment_variables = {
    METRICS_COLLECTION = "${var.fscollection_analysis}"
    MAX_TIME_MEANINGFUL_PAINT = "${var.max_time_to_meaningful_paint}"
  }
}
// [END function-analyzer-block]


// [START function-alerter-block]
data "archive_file" "local_alerter_source" {
  type        = "zip"
  source_dir  = "./functions/alerter"
  output_path = "${var.local_output_path}/alerter.zip"
}

resource "google_storage_bucket_object" "gcs_alerter_source" {
  name   = "alerter.zip"
  bucket = "${google_storage_bucket.bucket_source_archives.name}"
  source = "${data.archive_file.local_alerter_source.output_path}"
}

resource "google_cloudfunctions_function" "function_alerter" {
  name = "alerter-${var.suffix}"
  project = "${var.project_id}"
  region = "${var.region}"
  available_memory_mb = "256"
  entry_point = "generate_alert"
  runtime = "python37"
  source_archive_bucket = "${google_storage_bucket.bucket_source_archives.name}"
  source_archive_object = "${google_storage_bucket_object.gcs_alerter_source.name}"
  event_trigger {
    event_type = "providers/cloud.firestore/eventTypes/document.create"
    resource = "${var.fscollection_analysis}/{any}"
  }
  environment_variables = {
    ALERT_TOPIC = "${google_pubsub_topic.topic_alerts.name}"
  }
}
// [END function-alerter-block]
// [END all-functions-block]


// define output variables for use downstream
output "project" {
  value = "${var.project_id}"
}
output "region" {
  value = "${var.region}"
}
output "bucket_metrics" {
  value = "${google_storage_bucket.bucket_metrics.name}"
}
output "pubsub_subscription_alerts" {
  value = "${google_pubsub_subscription.subscription_alerts.name}"
}
output "function_tracer" {
  value = "${google_cloudfunctions_function.function_tracer.name}"
}
