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

const puppeteer = require('puppeteer');
const {Storage} = require('@google-cloud/storage');
const Url = require('url');

const metricsBucket = process.env.BUCKET_METRICS;
const allowedHosts = process.env.ALLOWED_HOSTS;

let gcs;


/**
 * Cloud Function entry point, HTTP trigger.
 * Loads the requested URL via Puppeteer, captures page performance
 * metrics, and writes to GCS buckets.
 *
 * @param {Object} req Cloud Function request context.
 * @param {Object} res Cloud Function response context.
 */
exports.trace = async (req, res) => {
  const url = getUrl(req);
  if (!url || !url.hostname) {
    console.error('Valid URL to trace not specified')
    return res.status(400).send('Please specify a valid URL to trace');
  }
  // allow analysis only of known domains
  if (!url.hostname.match(allowedHosts)) {
    console.error('Analysis of '+url.hostname+' not permitted. See ALLOWED_HOSTS variable');
    return res.status(400).send('Analysis of '+url.hostname+' not permitted');
  }

  let browser;
  const filename = new Date().toISOString();
  try {
    // [START puppeteer-block]
    // launch Puppeteer and start a Chrome DevTools Protocol (CDP) session
    // with performance tracking enabled.
    browser = await puppeteer.launch({
      headless: true,
      args: ['--no-sandbox']
    });
    const page = await browser.newPage();
    const client = await page.target().createCDPSession();
    await client.send('Performance.enable');

    // browse to the page, capture and write the performance metrics
    console.log('Fetching url: '+url.href);
    await page.goto(url.href, {
      'waitUntil' : 'networkidle0'
    });
    const performanceMetrics = await client.send('Performance.getMetrics');
    options = createUploadOptions('application/json', page.url());
    await writeToGcs(metricsBucket, filename, JSON.stringify(performanceMetrics), options);
    // [END puppeteer-block]

    res.status(200).send({
      url: page.url,
      filename: filename
    });
  } catch (e) {
    console.error('Caught Error: '+e);
    res.status(500).send(e);
  } finally {
    if (browser) {
      await browser.close();
    }
  }
}

async function writeToGcs(bucketName, filename, content, options) {
  gcs = gcs || new Storage();
  const bucket = gcs.bucket(bucketName);
  const file = bucket.file(filename);
  const gcs_filename = `gs://${bucket.name}/${file.name}`

  const stream = file.createWriteStream(options);
  return new Promise((resolve, reject) => {
    stream.end(content);
    stream.on('error', (err) => {
      console.error('Error writing GCS file: ' + err);
      reject(err);
    });
    stream.on('finish', () => {
      console.log('Created object: '+gcs_filename);
      resolve(200);
    });
  });
}

function createUploadOptions(contentType, url) {
  return {
    resumable: false,
    metadata: {
      contentType: contentType,
      metadata: {
        pageUrl: url,
      }
    }
  };
}

function getUrl(req) {
  if (req.query.url || req.body.url) {
    return Url.parse(req.query.url || req.body.url);
  }
  try {
    return Url.parse(JSON.parse(req.body).url);
  } catch (e) {}
}
