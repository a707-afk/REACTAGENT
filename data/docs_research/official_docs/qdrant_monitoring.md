<!-- source: Qdrant Monitoring -->
<!-- cleaned: nav-bar removed -->

# Monitoring & Telemetry


Qdrant exposes its metrics in Prometheus/OpenMetrics format, so you can integrate them easily
with the compatible tools and monitor Qdrant with your own monitoring system. You can
use the `/metrics` endpoint and configure it as a scrape target.

Metrics endpoint: http://localhost:6333/metrics

The integration with Qdrant is easy to
configure
with Prometheus and Grafana.
## Metrics


Qdrant exposes various metrics in Prometheus/OpenMetrics format, commonly used together with Grafana for monitoring.

Two endpoints are available:

`/metrics` for metrics of a Qdrant node/peer, see all metrics.

`/sys_metrics` (Qdrant Cloud only) for metrics about your cluster, like CPU, memory, disk utilisation, collection metrics and load balancer telemetry. For more information, see Qdrant Cloud Monitoring.

Note that `/metrics` only reports metrics for the peer connected to. It is therefore important to scrape from each peer individually, even if a load balancer is involved.
### Node Metrics `/metrics`


Each Qdrant node will expose the following metrics.

Counters - such as the number of created snapshots - are reset when the node is restarted.

Application MetricsNameTypeMeaningapp_infogaugeQdrant server name and versionapp_status_recovery_modegaugeIf started in recovery mode

Collection MetricsNameTypeMeaningcollections_totalgaugeNumber of collectionscollection_pointsgaugeNumber of points, per collection (v1.16+)collection_vectorsgaugeNumber of vectors, per collection and vector name (v1.16+)collections_vector_totalgaugeNumber of vectors in all collectionscollection_indexed_only_excluded_pointsgaugeNumber of points excluded in `indexed_only` search, per collection and vector name (v1.16+)collection_active_replicas_mingaugeMinimum number of active replicas across all collections and shards (v1.16+)collection_active_replicas_maxgaugeMaximum number of active replicas across all collections and shards (v1.16+)collection_dead_replicasgaugeNumber of non-active replicas across all collections and shards (v1.16+)collection_running_optimizationsgaugeNumber of running optimization tasks, per collection (v1.16+)collection_hardware_metric_cpucounterCPU measurements of a collection, per collection (v1.13+) 1collection_hardware_metric_payload_io_readcounterPayload IO read operations measurement, per collection (v1.13+) 1collection_hardware_metric_payload_io_writecounterPayload IO write operations measurement, per collection (v1.13+) 1collection_hardware_metric_payload_index_io_readcounterPayload index read operations measurement, per collection (v1.13+) 1collection_hardware_metric_payload_index_io_writecounterPayload index write operations measurement, per collection (v1.13+) 1collection_hardware_metric_vector_io_readcounterVector IO read operations measurement, per collection (v1.13+) 1collection_hardware_metric_vector_io_writecounterVector IO write operations measurement, per collection (v1.13+) 1

Snapshot MetricsNameTypeMeaningsnapshot_creation_runninggaugeNumber of snapshots being created, per collection (v1.16+)snapshot_recovery_runninggaugeNumber of snapshots being recovered, per collection (v1.16+)snapshot_created_totalcounterNumber of created snapshots since start, per collection (v1.16+)

API Response MetricsNameTypeMeaningrest_responses_totalcounterNumber of responses through REST API 2rest_responses_fail_totalcounterNumber of failed responses through REST APIrest_responses_avg_duration_secondsgaugeAverage response duration in REST APIrest_responses_min_duration_secondsgaugeMinimum response duration in REST APIrest_responses_max_duration_secondsgaugeMaximum response duration in REST APIrest_responses_duration_secondshistogramHistogram of response durations in the REST API (v1.8+)grpc_responses_totalcounterNumber of responses through gRPC API 2grpc_responses_fail_totalcounterNumber of failed responses through REST APIgrpc_responses_avg_duration_secondsgaugeAverage response duration in gRPC APIgrpc_responses_min_duration_secondsgaugeMinimum response duration in gRPC APIgrpc_responses_max_duration_secondsgaugeMaximum response duration in gRPC APIgrpc_responses_duration_secondshistogramHistogram of response durations in the gRPC API (v1.8+)

The output does not include metrics for the collection info, listing, and snapshot endpoints.

Process MetricsNameTypeMeaningmemory_active_bytesgaugeTotal number of bytes in active pages allocated by the application (ref)memory_allocated_bytesgaugeTotal number of bytes allocated by the application (ref)memory_metadata_bytesgaugeTotal number of bytes dedicated to allocator metadata (ref)memory_resident_bytesgaugeMaximum number of bytes in physically resident data pages mapped (ref)memory_retained_bytesgaugeTotal number of bytes in virtual memory mappings (ref)process_threadsgaugeNumber of used system threads (v1.16+)process_open_mmapsgaugeNumber of open memory maps (v1.16+)system_max_mmapsgaugeSystem wide maximum number of open memory maps (v1.16+)process_open_fdsgaugeNumber of open file descriptors (v1.16+)process_max_fdsgaugeMaximum number of open file descriptors (v1.16+)process_minor_page_faults_totalcounterNumber of minor page faults encountered by the process (v1.16+)process_major_page_faults_totalcounterNumber of major page faults encountered by the process (v1.16+)

Cluster Metrics (Consensus)

Metrics reporting the current cluster consensus state of the node. Exposed only
when distributed mode is enabled.NameTypeMeaningcluster_enabledgaugeIf distributed mode is enabled 3cluster_peers_totalgaugeNumber of cluster peers 3cluster_termcounterRaft consensus term 3cluster_commitcounterRaft consensus commit - last committed operation 3cluster_pending_operations_totalgaugeNumber of pending consensus operations 3cluster_votergaugeIf a consensus voter (`1`) or learner (`) 3
### Metrics Configuration


Available as of v1.16.0

In self-hosted environments you have further configuration options for metrics.

By default, all Qdrant metrics have no application namespace prefix. You may set
a prefix with `service.metrics_prefix` in the
configuration.

To achieve this you may use the following environment variable for example:

`QDRANT__SERVICE__METRICS_PREFIX="qdrant_"
`
### Per-Collection API Metrics


Available as of v1.18.0

By default, the API response metrics (est_responses_*`, `grpc_responses_*`) are global — they don’t distinguish between collections. To request per-collection breakdowns, add `?per_collection=true` to the `/metrics` endpoint:

`curl http://localhost:6333/metrics?per_collection=true
`

Enabling per-collection mode replaces the global metrics entirely. The unlabeled est_responses_total` and `grpc_responses_total` are not returned when per-collection data is enabled. Instead, est_responses_total` carries four labels (`method`, `endpoint`, `status`, `collection`) and `grpc_responses_total` carries three (`endpoint`, `status`, `collection`):

est_responses_total{method="POST",endpoint="/collections/{collection_name}/points/search",status="200",collection="my-collection"} 42
grpc_responses_total{endpoint="/qdrant.Points/Search",status="0",collection="my-collection"} 17
`

The `endpoint` label uses the route template, not the resolved path. The actual collection name is in the separate `collection` label.
## Telemetry Endpoint


Qdrant also provides a `/telemetry` endpoint, which provides information about the current state of the database, including the number of vectors, shards, and other useful information. You can find the full documentation for this endpoint in the API reference.
## Cluster-Wide Telemetry


The `/telemetry` endpoint reports from the point of view of the peer being queried. Qdrant also provides a `/cluster/telemetry` endpoint, which aggregates telemetry from all peers.

This includes less information than `/telemetry`, but provides information like shard transfer progress more reliably.
You can find the full documentation for this endpoint in the API reference.
## Kubernetes Health Endpoints


Available as of v1.5.0

Qdrant exposes three endpoints, namely
`/healthz`,
`/livez` and
`/readyz`, to indicate the current status of the
Qdrant server.

These currently provide the most basic status response, returning HTTP 200 if
Qdrant is started and ready to be used.

Regardless of whether an API key is configured,
the endpoints are always accessible.

You can read more about Kubernetes health endpoints
here.

Only reported if hardware metrics are enabled in the configuration. See `service.hardware_reporting` in the configuration. ↩︎ ↩︎ ↩︎ ↩︎ ↩︎ ↩︎ ↩︎

When `/metrics?per_collection=true` is used, these metrics include a `collection` label. See Per-Collection API Metrics. ↩︎ ↩︎

Only reported if distributed mode (cluster mode) is enabled. Enabled by default in all Qdrant Cloud environments. See `cluster.enabled` in the configuration. ↩︎ ↩︎ ↩︎ ↩︎ ↩︎ ↩︎
##### Was this page useful?


Yes


No

Thank you for your feedback! 🙏

We are sorry to hear that. 😔 You can edit this page on GitHub, or create a GitHub issue.


Create an issue
