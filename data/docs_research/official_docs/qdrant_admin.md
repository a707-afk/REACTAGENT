<!-- source: Qdrant Admin -->
<!-- cleaned: nav-bar removed -->

# Administration


Qdrant exposes administration tools which enable to modify at runtime the behavior of a qdrant instance without changing its configuration manually.
## Recovery Mode


Available as of v1.2.0

Recovery mode can help in situations where Qdrant fails to start repeatedly.
When starting in recovery mode, Qdrant only loads collection metadata to prevent
going out of memory. This allows you to resolve out of memory situations, for
example, by deleting a collection. After resolving Qdrant can be restarted
normally to continue operation.

In recovery mode, collection operations are limited to
deleting a
collection. That is because only collection metadata is loaded during recovery.

To enable recovery mode with the Qdrant Docker image you must set the
environment variable `QDRANT_ALLOW_RECOVERY_MODE=true`. The container will try
to start normally first, and restarts in recovery mode if initialisation fails
due to an out of memory error. This behavior is disabled by default.

If using a Qdrant binary, recovery mode can be enabled by setting a recovery
message in an environment variable, such as
`QDRANT__STORAGE__RECOVERY_MODE="My recovery message"`.
## Low Memory Mode


Available as of v1.18.0

Low memory mode reduces memory requirements at startup. On memory-constrained hosts, the normal startup process can exhaust available memory before the node becomes reachable resulting in a crash loop. Low memory mode lets you bring the node up with a reduced memory footprint so you can make configuration changes to reduce memory usage. Revert it once the node is stable.

Three modes are available:ModeDescription`disabled`Default. Loads all components as persisted.o_resident`Forces quantization to behave as lways_ram: false`, payload field indexes to `on_disk: true`, and payload storage to mmap with lazy populate.o_populate`Same as o_resident`, and additionally skips mmap prefetch for vectors, the HNSW graph, and payload storage. Offers the lowest startup memory footprint, but first queries will be slower until the OS page cache warms up.

To enable low memory mode, set `storage.low_memory_mode` in the node’s configuration file:

`storage:
 low_memory_mode: no_populate # or no_resident
`

Or use the environment variable:

`QDRANT__STORAGE__LOW_MEMORY_MODE=no_populate
`

Low memory mode takes effect on the next restart. It doesn’t modify the vector storage settings persisted in your collections.
## Strict Mode


Available as of v1.13.0

Strict mode is a feature to restrict certain type of operations on a collection in order to protect the Qdrant cluster. The goal is to prevent inefficient usage patterns that could overload the system.

Strict mode ensures a more predictable and responsive service when you do not have control over the queries that are being executed. Upon crossing a limit, the server will return a client side error with the information about the limit that was crossed.

The `strict_mode_config` can be enabled when creating a new collection, see schema definitions for all the available `strict_mode_config` parameters. As part of the config, the `enabled` field act as a toggle to enable or disable the strict mode dynamically.

Simply enabling strict mode without specifying a specific restriction does not have any effect. You need to explicitly set the restrictions you want to enforce.

On Qdrant Cloud, strict mode is enabled by default for new collections. Refer to Configure Qdrant Cloud Clusters for the specific restrictions.

It is possible to raise the default limits and/or disable strict mode entirely. Though, in order to ensure a stable cluster we strongly recommend to keep strict mode enabled using its default configuration. For disabling strict mode on an existing collection use:

`PUT /collections/{collection_name}
{
 "strict_mode_config": {
 "enabled": false
 }
}
`

`curl -X PUT http://localhost:6333/collections/{collection_name} \
 -H 'Content-Type: application/json' \
 --data-raw '{
 "strict_mode_config": {
 "enabled":" false
 }
 }'
`

`from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
 collection_name="{collection_name}",
 strict_mode_config=models.StrictModeConfig(enabled=False),
)
`

`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.createCollection("{collection_name}", {
 strict_mode_config: {
 enabled: false,
 },
});
`

`use qdrant_client::Qdrant;
use qdrant_client::qdrant::{CreateCollectionBuilder, StrictModeConfigBuilder};

let client = Qdrant::from_url("http://localhost:6334").build()?;

client
 .create_collection(
 CreateCollectionBuilder::new("{collection_name}")
 .strict_mode_config(StrictModeConfigBuilder::default().enabled(false)),
 )
 .await?;
`

`import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Collections.CreateCollection;
import io.qdrant.client.grpc.Collections.StrictModeConfig;

QdrantClient client =
 new QdrantClient(QdrantGrpcClient.newBuilder("localhost", 6334, false).build());

client
 .createCollectionAsync(
 CreateCollection.newBuilder()
 .setCollectionName("{collection_name}")
 .setStrictModeConfig(
 StrictModeConfig.newBuilder().setEnabled(false).build())
 .build())
 .get();
`

`using Qdrant.Client;
using Qdrant.Client.Grpc;

var client = new QdrantClient("localhost", 6334);

await client.CreateCollectionAsync(
 collectionName: "{collection_name}",
 strictModeConfig: new StrictModeConfig { Enabled = false }
);
`

`import (
 "context"

 "github.com/qdrant/go-client/qdrant"
)

client, err := qdrant.NewClient(&qdrant.Config{
 Host: "localhost",
 Port: 6334,
})

client.CreateCollection(context.Background(), &qdrant.CreateCollection{
 CollectionName: "{collection_name}",
 StrictModeConfig: &qdrant.StrictModeConfig{
 Enabled: qdrant.PtrOf(false),
 },
})
`
### Disable Retrieving via Non Indexed Payload


Setting `unindexed_filtering_retrieve` to false prevents retrieving points by filtering on a non indexed payload key which can be very slow.

`PUT /collections/{collection_name}
{
 "strict_mode_config": {
 "enabled": true,
 "unindexed_filtering_retrieve": false
 }
}
`

`curl -X PUT http://localhost:6333/collections/{collection_name} \
 -H 'Content-Type: application/json' \
 --data-raw '{
 "strict_mode_config": {
 "enabled":" true,
 "unindexed_filtering_retrieve": false
 }
 }'
`

`from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
 collection_name="{collection_name}",
 strict_mode_config=models.StrictModeConfig(enabled=True, unindexed_filtering_retrieve=False),
)
`

`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.createCollection("{collection_name}", {
 strict_mode_config: {
 enabled: true,
 unindexed_filtering_retrieve: false,
 },
});
`

`use qdrant_client::Qdrant;
use qdrant_client::qdrant::{CreateCollectionBuilder, StrictModeConfigBuilder};

let client = Qdrant::from_url("http://localhost:6334").build()?;

client
 .create_collection(
 CreateCollectionBuilder::new("{collection_name}")
 .strict_mode_config(StrictModeConfigBuilder::default().enabled(true).unindexed_filtering_retrieve(false)),
 )
 .await?;
`

`import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Collections.CreateCollection;
import io.qdrant.client.grpc.Collections.StrictModeConfig;

QdrantClient client =
 new QdrantClient(QdrantGrpcClient.newBuilder("localhost", 6334, false).build());

client
 .createCollectionAsync(
 CreateCollection.newBuilder()
 .setCollectionName("{collection_name}")
 .setStrictModeConfig(
 StrictModeConfig.newBuilder().setEnabled(true).setUnindexedFilteringRetrieve(false).build())
 .build())
 .get();
`

`using Qdrant.Client;
using Qdrant.Client.Grpc;

var client = new QdrantClient("localhost", 6334);

await client.CreateCollectionAsync(
 collectionName: "{collection_name}",
 strictModeConfig: new StrictModeConfig { Enabled = true, UnindexedFilteringRetrieve = false }
);
`

`import (
 "context"

 "github.com/qdrant/go-client/qdrant"
)

client, err := qdrant.NewClient(&qdrant.Config{
 Host: "localhost",
 Port: 6334,
})

client.CreateCollection(context.Background(), &qdrant.CreateCollection{
 CollectionName: "{collection_name}",
 StrictModeConfig: &qdrant.StrictModeConfig{
 Enabled: qdrant.PtrOf(true),
 UnindexedFilteringRetrieve: qdrant.PtrOf(false),
 },
})
`

Or turn it off later on an existing collection through the update collection parameters API.

`PATCH /collections/{collection_name}
{
 "strict_mode_config": {
 "enabled": true,
 "unindexed_filtering_retrieve": true
 }
}
`

`curl -X PATCH http://localhost:6333/collections/{collection_name} \
 -H 'Content-Type: application/json' \
 --data-raw '{
 "strict_mode_config": {
 "enabled": true,
 "unindexed_filtering_retrieve": true
 }
 }'
`

`client.update_collection(
 collection_name="{collection_name}",
 strict_mode_config=models.StrictModeConfig(
 enabled=True,
 unindexed_filtering_retrieve=True,
 ),
)
`

`client.updateCollection("{collection_name}", {
 strict_mode_config: {
 enabled: true,
 unindexed_filtering_retrieve: true,
 },
});
`

`use qdrant_client::qdrant::{UpdateCollectionBuilder, StrictModeConfigBuilder};

client
 .update_collection(
 UpdateCollectionBuilder::new("{collection_name}")
 .strict_mode_config(
 StrictModeConfigBuilder::default()
 .enabled(true)
 .unindexed_filtering_retrieve(true),
 ),
 )
 .await?;
`

`import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Collections.UpdateCollection;
import io.qdrant.client.grpc.Collections.StrictModeConfig;

client
 .updateCollectionAsync(
 UpdateCollection.newBuilder()
 .setCollectionName("{collection_name}")
 .setStrictModeConfig(
 StrictModeConfig.newBuilder()
 .setEnabled(true)
 .setUnindexedFilteringRetrieve(true)
 .build())
 .build())
 .get();
`

`using Qdrant.Client;
using Qdrant.Client.Grpc;

var client = new QdrantClient("localhost", 6334);

await client.UpdateCollectionAsync(
 collectionName: "{collection_name}",
 strictModeConfig: new StrictModeConfig
 {
 Enabled = true,
 UnindexedFilteringRetrieve = true,
 }
);
`

`import (
 "context"

 "github.com/qdrant/go-client/qdrant"
)

client.UpdateCollection(context.Background(), &qdrant.UpdateCollection{
 CollectionName: "{collection_name}",
 StrictModeConfig: &qdrant.StrictModeConfig{
 Enabled: qdrant.PtrOf(true),
 UnindexedFilteringRetrieve: qdrant.PtrOf(true),
 },
})
`
### Disable Updating via Non Indexed Payload


Setting `unindexed_filtering_update` to false prevents updating points by filtering on a non indexed payload key which can be very slow.

`PUT /collections/{collection_name}
{
 "strict_mode_config": {
 "enabled": true,
 "unindexed_filtering_update": false
 }
}
`

`curl -X PUT http://localhost:6333/collections/{collection_name} \
 -H 'Content-Type: application/json' \
 --data-raw '{
 "strict_mode_config": {
 "enabled":" true,
 "unindexed_filtering_update": false
 }
 }'
`

`from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
 collection_name="{collection_name}",
 strict_mode_config=models.StrictModeConfig(enabled=True, unindexed_filtering_update=False),
)
`

`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.createCollection("{collection_name}", {
 strict_mode_config: {
 enabled: true,
 unindexed_filtering_update: false,
 },
});
`

`use qdrant_client::Qdrant;
use qdrant_client::qdrant::{CreateCollectionBuilder, StrictModeConfigBuilder};

let client = Qdrant::from_url("http://localhost:6334").build()?;

client
 .create_collection(
 CreateCollectionBuilder::new("{collection_name}")
 .strict_mode_config(StrictModeConfigBuilder::default().enabled(true).unindexed_filtering_update(false)),
 )
 .await?;
`

`import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Collections.CreateCollection;
import io.qdrant.client.grpc.Collections.StrictModeConfig;

QdrantClient client =
 new QdrantClient(QdrantGrpcClient.newBuilder("localhost", 6334, false).build());

client
 .createCollectionAsync(
 CreateCollection.newBuilder()
 .setCollectionName("{collection_name}")
 .setStrictModeConfig(
 StrictModeConfig.newBuilder().setEnabled(true).setUnindexedFilteringUpdate(false).build())
 .build())
 .get();
`

`using Qdrant.Client;
using Qdrant.Client.Grpc;

var client = new QdrantClient("localhost", 6334);

await client.CreateCollectionAsync(
 collectionName: "{collection_name}",
 strictModeConfig: new StrictModeConfig { Enabled = true, UnindexedFilteringUpdate = false }
);
`

`import (
 "context"

 "github.com/qdrant/go-client/qdrant"
)

client, err := qdrant.NewClient(&qdrant.Config{
 Host: "localhost",
 Port: 6334,
})

client.CreateCollection(context.Background(), &qdrant.CreateCollection{
 CollectionName: "{collection_name}",
 StrictModeConfig: &qdrant.StrictModeConfig{
 Enabled: qdrant.PtrOf(true),
 UnindexedFilteringUpdate: qdrant.PtrOf(false),
 },
})
`
### Maximum Number of Payload Index Count


Setting `max_payload_index_count` caps the maximum number of payload index that can exist on a collection.

`PUT /collections/{collection_name}
{
 "strict_mode_config": {
 "enabled": true,
 "max_payload_index_count": 10
 }
}
`

`curl -X PUT http://localhost:6333/collections/{collection_name} \
 -H 'Content-Type: application/json' \
 --data-raw '{
 "strict_mode_config": {
 "enabled":" true,
 "max_payload_index_count": 10
 }
 }'
`

`from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
 collection_name="{collection_name}",
 strict_mode_config=models.StrictModeConfig(enabled=True, max_payload_index_count=10),
)
`

`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.createCollection("{collection_name}", {
 strict_mode_config: {
 enabled: true,
 max_payload_index_count: 10,
 },
});
`

`use qdrant_client::Qdrant;
use qdrant_client::qdrant::{CreateCollectionBuilder, StrictModeConfigBuilder};

let client = Qdrant::from_url("http://localhost:6334").build()?;

client
 .create_collection(
 CreateCollectionBuilder::new("{collection_name}")
 .strict_mode_config(StrictModeConfigBuilder::default().enabled(true).max_payload_index_count(10)),
 )
 .await?;
`

`import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Collections.CreateCollection;
import io.qdrant.client.grpc.Collections.StrictModeConfig;

QdrantClient client =
 new QdrantClient(QdrantGrpcClient.newBuilder("localhost", 6334, false).build());

client
 .createCollectionAsync(
 CreateCollection.newBuilder()
 .setCollectionName("{collection_name}")
 .setStrictModeConfig(
 StrictModeConfig.newBuilder().setEnabled(true).setMaxPayloadIndexCount(10).build())
 .build())
 .get();
`

`using Qdrant.Client;
using Qdrant.Client.Grpc;

var client = new QdrantClient("localhost", 6334);

await client.CreateCollectionAsync(
 collectionName: "{collection_name}",
 strictModeConfig: new StrictModeConfig { Enabled = true, MaxPayloadIndexCount = 10 }
);
`

`import (
 "context"

 "github.com/qdrant/go-client/qdrant"
)

client, err := qdrant.NewClient(&qdrant.Config{
 Host: "localhost",
 Port: 6334,
})

client.CreateCollection(context.Background(), &qdrant.CreateCollection{
 CollectionName: "{collection_name}",
 StrictModeConfig: &qdrant.StrictModeConfig{
 Enabled: qdrant.PtrOf(true),
 MaxPayloadIndexCount: qdrant.PtrOf(uint64(10)),
 },
})
`
### Maximum Query `limit` Parameter


Retrieving large result set is expensive.

Setting `max_query_limit` caps the maximum number of points that can be retrieved in a single query.

`PUT /collections/{collection_name}
{
 "strict_mode_config": {
 "enabled": true,
 "max_query_limit": 10
 }
}
`

`curl -X PUT http://localhost:6333/collections/{collection_name} \
 -H 'Content-Type: application/json' \
 --data-raw '{
 "strict_mode_config": {
 "enabled":" true,
 "max_query_limit": 10
 }
 }'
`

`from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
 collection_name="{collection_name}",
 strict_mode_config=models.StrictModeConfig(enabled=True, max_query_limit=10),
)
`

`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.createCollection("{collection_name}", {
 strict_mode_config: {
 enabled: true,
 max_query_limit: 10,
 },
});
`

`use qdrant_client::Qdrant;
use qdrant_client::qdrant::{CreateCollectionBuilder, StrictModeConfigBuilder};

let client = Qdrant::from_url("http://localhost:6334").build()?;

client
 .create_collection(
 CreateCollectionBuilder::new("{collection_name}")
 .strict_mode_config(StrictModeConfigBuilder::default().enabled(true).max_query_limit(10)),
 )
 .await?;
`

`import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Collections.CreateCollection;
import io.qdrant.client.grpc.Collections.StrictModeConfig;

QdrantClient client =
 new QdrantClient(QdrantGrpcClient.newBuilder("localhost", 6334, false).build());

client
 .createCollectionAsync(
 CreateCollection.newBuilder()
 .setCollectionName("{collection_name}")
 .setStrictModeConfig(
 StrictModeConfig.newBuilder().setEnabled(true).setMaxQueryLimit(10).build())
 .build())
 .get();
`

`using Qdrant.Client;
using Qdrant.Client.Grpc;

var client = new QdrantClient("localhost", 6334);

await client.CreateCollectionAsync(
 collectionName: "{collection_name}",
 strictModeConfig: new StrictModeConfig { Enabled = true, MaxQueryLimit = 10 }
);
`

`import (
 "context"

 "github.com/qdrant/go-client/qdrant"
)

client, err := qdrant.NewClient(&qdrant.Config{
 Host: "localhost",
 Port: 6334,
})

client.CreateCollection(context.Background(), &qdrant.CreateCollection{
 CollectionName: "{collection_name}",
 StrictModeConfig: &qdrant.StrictModeConfig{
 Enabled: qdrant.PtrOf(true),
 MaxQueryLimit: qdrant.PtrOf(uint32(10)),
 },
})
`
### Maximum imeout` Parameter


Long running operations are often symptomatic of a deeper issue.

Setting `max_timeout` caps the maximum value in seconds for the imeout` parameter in all API operations.

`PUT /collections/{collection_name}
{
 "strict_mode_config": {
 "enabled": true,
 "max_timeout": 10
 }
}
`

`curl -X PUT http://localhost:6333/collections/{collection_name} \
 -H 'Content-Type: application/json' \
 --data-raw '{
 "strict_mode_config": {
 "enabled":" true,
 "max_timeout": 10
 }
 }'
`

`from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
 collection_name="{collection_name}",
 strict_mode_config=models.StrictModeConfig(enabled=True, max_timeout=10),
)
`

`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.createCollection("{collection_name}", {
 strict_mode_config: {
 enabled: true,
 max_timeout: 10,
 },
});
`

`use qdrant_client::Qdrant;
use qdrant_client::qdrant::{CreateCollectionBuilder, StrictModeConfigBuilder};

let client = Qdrant::from_url("http://localhost:6334").build()?;

client
 .create_collection(
 CreateCollectionBuilder::new("{collection_name}")
 .strict_mode_config(StrictModeConfigBuilder::default().enabled(true).max_timeout(10)),
 )
 .await?;
`

`import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Collections.CreateCollection;
import io.qdrant.client.grpc.Collections.StrictModeConfig;

QdrantClient client =
 new QdrantClient(QdrantGrpcClient.newBuilder("localhost", 6334, false).build());

client
 .createCollectionAsync(
 CreateCollection.newBuilder()
 .setCollectionName("{collection_name}")
 .setStrictModeConfig(
 StrictModeConfig.newBuilder().setEnabled(true).setMaxTimeout(10).build())
 .build())
 .get();
`

`using Qdrant.Client;
using Qdrant.Client.Grpc;

var client = new QdrantClient("localhost", 6334);

await client.CreateCollectionAsync(
 collectionName: "{collection_name}",
 strictModeConfig: new StrictModeConfig { Enabled = true, MaxTimeout = 10 }
);
`

`import (
 "context"

 "github.com/qdrant/go-client/qdrant"
)

client, err := qdrant.NewClient(&qdrant.Config{
 Host: "localhost",
 Port: 6334,
})

client.CreateCollection(context.Background(), &qdrant.CreateCollection{
 CollectionName: "{collection_name}",
 StrictModeConfig: &qdrant.StrictModeConfig{
 Enabled: qdrant.PtrOf(true),
 MaxTimeout: qdrant.PtrOf(uint32(10)),
 },
})
`
### Disable Exact Search


Exact search bypasses the HNSW index and performs a brute-force scan, which can be very slow on large collections.

Setting `search_allow_exact` to false prevents clients from requesting exact search.

`PUT /collections/{collection_name}
{
 "strict_mode_config": {
 "enabled": true,
 "search_allow_exact": false
 }
}
`

`curl -X PUT http://localhost:6333/collections/{collection_name} \
 -H 'Content-Type: application/json' \
 --data-raw '{
 "strict_mode_config": {
 "enabled": true,
 "search_allow_exact": false
 }
 }'
`

`from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
 collection_name="{collection_name}",
 strict_mode_config=models.StrictModeConfig(enabled=True, search_allow_exact=False),
)
`

`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.createCollection("{collection_name}", {
 strict_mode_config: {
 enabled: true,
 search_allow_exact: false,
 },
});
`

`use qdrant_client::Qdrant;
use qdrant_client::qdrant::{CreateCollectionBuilder, StrictModeConfigBuilder};

let client = Qdrant::from_url("http://localhost:6334").build()?;

client
 .create_collection(
 CreateCollectionBuilder::new("{collection_name}")
 .strict_mode_config(StrictModeConfigBuilder::default().enabled(true).search_allow_exact(false)),
 )
 .await?;
`

`import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Collections.CreateCollection;
import io.qdrant.client.grpc.Collections.StrictModeConfig;

QdrantClient client =
 new QdrantClient(QdrantGrpcClient.newBuilder("localhost", 6334, false).build());

client
 .createCollectionAsync(
 CreateCollection.newBuilder()
 .setCollectionName("{collection_name}")
 .setStrictModeConfig(
 StrictModeConfig.newBuilder().setEnabled(true).setSearchAllowExact(false).build())
 .build())
 .get();
`

`using Qdrant.Client;
using Qdrant.Client.Grpc;

var client = new QdrantClient("localhost", 6334);

await client.CreateCollectionAsync(
 collectionName: "{collection_name}",
 strictModeConfig: new StrictModeConfig { Enabled = true, SearchAllowExact = false }
);
`

`import (
 "context"

 "github.com/qdrant/go-client/qdrant"
)

client, err := qdrant.NewClient(&qdrant.Config{
 Host: "localhost",
 Port: 6334,
})

client.CreateCollection(context.Background(), &qdrant.CreateCollection{
 CollectionName: "{collection_name}",
 StrictModeConfig: &qdrant.StrictModeConfig{
 Enabled: qdrant.PtrOf(true),
 SearchAllowExact: qdrant.PtrOf(false),
 },
})
`
### Maximum HNSW ef Parameter


A high HNSW `ef` value increases recall but also increases search latency.

Setting `search_max_hnsw_ef` caps the maximum `ef` value allowed in search parameters.

`PUT /collections/{collection_name}
{
 "strict_mode_config": {
 "enabled": true,
 "search_max_hnsw_ef": 128
 }
}
`

`curl -X PUT http://localhost:6333/collections/{collection_name} \
 -H 'Content-Type: application/json' \
 --data-raw '{
 "strict_mode_config": {
 "enabled": true,
 "search_max_hnsw_ef": 128
 }
 }'
`

`from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
 collection_name="{collection_name}",
 strict_mode_config=models.StrictModeConfig(enabled=True, search_max_hnsw_ef=128),
)
`

`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.createCollection("{collection_name}", {
 strict_mode_config: {
 enabled: true,
 search_max_hnsw_ef: 128,
 },
});
`

`use qdrant_client::Qdrant;
use qdrant_client::qdrant::{CreateCollectionBuilder, StrictModeConfigBuilder};

let client = Qdrant::from_url("http://localhost:6334").build()?;

client
 .create_collection(
 CreateCollectionBuilder::new("{collection_name}")
 .strict_mode_config(StrictModeConfigBuilder::default().enabled(true).search_max_hnsw_ef(128u32)),
 )
 .await?;
`

`import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Collections.CreateCollection;
import io.qdrant.client.grpc.Collections.StrictModeConfig;

QdrantClient client =
 new QdrantClient(QdrantGrpcClient.newBuilder("localhost", 6334, false).build());

client
 .createCollectionAsync(
 CreateCollection.newBuilder()
 .setCollectionName("{collection_name}")
 .setStrictModeConfig(
 StrictModeConfig.newBuilder().setEnabled(true).setSearchMaxHnswEf(128).build())
 .build())
 .get();
`

`using Qdrant.Client;
using Qdrant.Client.Grpc;

var client = new QdrantClient("localhost", 6334);

await client.CreateCollectionAsync(
 collectionName: "{collection_name}",
 strictModeConfig: new StrictModeConfig { Enabled = true, SearchMaxHnswEf = 128 }
);
`

`import (
 "context"

 "github.com/qdrant/go-client/qdrant"
)

client, err := qdrant.NewClient(&qdrant.Config{
 Host: "localhost",
 Port: 6334,
})

client.CreateCollection(context.Background(), &qdrant.CreateCollection{
 CollectionName: "{collection_name}",
 StrictModeConfig: &qdrant.StrictModeConfig{
 Enabled: qdrant.PtrOf(true),
 SearchMaxHnswEf: qdrant.PtrOf(uint32(128)),
 },
})
`
### Maximum Search Oversampling


A high oversampling factor increases the number of candidates evaluated during search, which can significantly increase latency.

Setting `search_max_oversampling` caps the maximum oversampling factor allowed in search parameters.

`PUT /collections/{collection_name}
{
 "strict_mode_config": {
 "enabled": true,
 "search_max_oversampling": 2.0
 }
}
`

`curl -X PUT http://localhost:6333/collections/{collection_name} \
 -H 'Content-Type: application/json' \
 --data-raw '{
 "strict_mode_config": {
 "enabled": true,
 "search_max_oversampling": 2.0
 }
 }'
`

`from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
 collection_name="{collection_name}",
 strict_mode_config=models.StrictModeConfig(enabled=True, search_max_oversampling=2.0),
)
`

`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.createCollection("{collection_name}", {
 strict_mode_config: {
 enabled: true,
 search_max_oversampling: 2.0,
 },
});
`

`use qdrant_client::Qdrant;
use qdrant_client::qdrant::{CreateCollectionBuilder, StrictModeConfigBuilder};

let client = Qdrant::from_url("http://localhost:6334").build()?;

client
 .create_collection(
 CreateCollectionBuilder::new("{collection_name}")
 .strict_mode_config(StrictModeConfigBuilder::default().enabled(true).search_max_oversampling(2.0f32)),
 )
 .await?;
`

`import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Collections.CreateCollection;
import io.qdrant.client.grpc.Collections.StrictModeConfig;

QdrantClient client =
 new QdrantClient(QdrantGrpcClient.newBuilder("localhost", 6334, false).build());

client
 .createCollectionAsync(
 CreateCollection.newBuilder()
 .setCollectionName("{collection_name}")
 .setStrictModeConfig(
 StrictModeConfig.newBuilder().setEnabled(true).setSearchMaxOversampling(2.0f).build())
 .build())
 .get();
`

`using Qdrant.Client;
using Qdrant.Client.Grpc;

var client = new QdrantClient("localhost", 6334);

await client.CreateCollectionAsync(
 collectionName: "{collection_name}",
 strictModeConfig: new StrictModeConfig { Enabled = true, SearchMaxOversampling = 2.0f }
);
`

`import (
 "context"

 "github.com/qdrant/go-client/qdrant"
)

client, err := qdrant.NewClient(&qdrant.Config{
 Host: "localhost",
 Port: 6334,
})

client.CreateCollection(context.Background(), &qdrant.CreateCollection{
 CollectionName: "{collection_name}",
 StrictModeConfig: &qdrant.StrictModeConfig{
 Enabled: qdrant.PtrOf(true),
 SearchMaxOversampling: qdrant.PtrOf(float32(2.0)),
 },
})
`
### Maximum Size of a Filtering Condition


Large filtering conditions are expensive to evaluate.

Setting `condition_max_size` caps the maximum number of element a filtering condition can have.

e.g. the number of elements in `MatchAny`

`PUT /collections/{collection_name}
{
 "strict_mode_config": {
 "enabled": true,
 "condition_max_size": 10
 }
}
`

`curl -X PUT http://localhost:6333/collections/{collection_name} \
 -H 'Content-Type: application/json' \
 --data-raw '{
 "strict_mode_config": {
 "enabled":" true,
 "condition_max_size": 10
 }
 }'
`

`from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
 collection_name="{collection_name}",
 strict_mode_config=models.StrictModeConfig(enabled=True, condition_max_size=10),
)
`

`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.createCollection("{collection_name}", {
 strict_mode_config: {
 enabled: true,
 condition_max_size: 10,
 },
});
`

`use qdrant_client::Qdrant;
use qdrant_client::qdrant::{CreateCollectionBuilder, StrictModeConfigBuilder};

let client = Qdrant::from_url("http://localhost:6334").build()?;

client
 .create_collection(
 CreateCollectionBuilder::new("{collection_name}")
 .strict_mode_config(StrictModeConfigBuilder::default().enabled(true).condition_max_size(10)),
 )
 .await?;
`

`import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Collections.CreateCollection;
import io.qdrant.client.grpc.Collections.StrictModeConfig;

QdrantClient client =
 new QdrantClient(QdrantGrpcClient.newBuilder("localhost", 6334, false).build());

client
 .createCollectionAsync(
 CreateCollection.newBuilder()
 .setCollectionName("{collection_name}")
 .setStrictModeConfig(
 StrictModeConfig.newBuilder().setEnabled(true).setConditionMaxSize(10).build())
 .build())
 .get();
`

`using Qdrant.Client;
using Qdrant.Client.Grpc;

var client = new QdrantClient("localhost", 6334);

await client.CreateCollectionAsync(
 collectionName: "{collection_name}",
 strictModeConfig: new StrictModeConfig { Enabled = true, ConditionMaxSize = 10 }
);
`

`import (
 "context"

 "github.com/qdrant/go-client/qdrant"
)

client, err := qdrant.NewClient(&qdrant.Config{
 Host: "localhost",
 Port: 6334,
})

client.CreateCollection(context.Background(), &qdrant.CreateCollection{
 CollectionName: "{collection_name}",
 StrictModeConfig: &qdrant.StrictModeConfig{
 Enabled: qdrant.PtrOf(true),
 ConditionMaxSize: qdrant.PtrOf(uint64(10)),
 },
})
`
### Maximum Number of Conditions in a Filter


A large number of filtering conditions are expensive to evaluate.

Setting `filter_max_conditions` caps the maximum number of conditions filters can have.

`PUT /collections/{collection_name}
{
 "strict_mode_config": {
 "enabled": true,
 "filter_max_conditions": 10
 }
}
`

`curl -X PUT http://localhost:6333/collections/{collection_name} \
 -H 'Content-Type: application/json' \
 --data-raw '{
 "strict_mode_config": {
 "enabled":" true,
 "filter_max_conditions": 10
 }
 }'
`

`from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
 collection_name="{collection_name}",
 strict_mode_config=models.StrictModeConfig(enabled=True, filter_max_conditions=10),
)
`

`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.createCollection("{collection_name}", {
 strict_mode_config: {
 enabled: true,
 filter_max_conditions: 10,
 },
});
`

`use qdrant_client::Qdrant;
use qdrant_client::qdrant::{CreateCollectionBuilder, StrictModeConfigBuilder};

let client = Qdrant::from_url("http://localhost:6334").build()?;

client
 .create_collection(
 CreateCollectionBuilder::new("{collection_name}")
 .strict_mode_config(StrictModeConfigBuilder::default().enabled(true).filter_max_conditions(10)),
 )
 .await?;
`

`import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Collections.CreateCollection;
import io.qdrant.client.grpc.Collections.StrictModeConfig;

QdrantClient client =
 new QdrantClient(QdrantGrpcClient.newBuilder("localhost", 6334, false).build());

client
 .createCollectionAsync(
 CreateCollection.newBuilder()
 .setCollectionName("{collection_name}")
 .setStrictModeConfig(
 StrictModeConfig.newBuilder().setEnabled(true).setFilterMaxConditions(10).build())
 .build())
 .get();
`

`using Qdrant.Client;
using Qdrant.Client.Grpc;

var client = new QdrantClient("localhost", 6334);

await client.CreateCollectionAsync(
 collectionName: "{collection_name}",
 strictModeConfig: new StrictModeConfig { Enabled = true, FilterMaxConditions = 10 }
);
`

`import (
 "context"

 "github.com/qdrant/go-client/qdrant"
)

client, err := qdrant.NewClient(&qdrant.Config{
 Host: "localhost",
 Port: 6334,
})

client.CreateCollection(context.Background(), &qdrant.CreateCollection{
 CollectionName: "{collection_name}",
 StrictModeConfig: &qdrant.StrictModeConfig{
 Enabled: qdrant.PtrOf(true),
 FilterMaxConditions: qdrant.PtrOf(uint64(10)),
 },
})
`
### Maximum Batch Size When Inserting Vectors


Sending very large batch upserts can create internal congestion.

Setting `upsert_max_batchsize` caps the maximum size in bytes of a batch during vector upserts.

`PUT /collections/{collection_name}
{
 "strict_mode_config": {
 "enabled": true,
 "upsert_max_batchsize": 1000
 }
}
`

`curl -X PUT http://localhost:6333/collections/{collection_name} \
 -H 'Content-Type: application/json' \
 --data-raw '{
 "strict_mode_config": {
 "enabled":" true,
 "upsert_max_batchsize": 1000
 }
 }'
`

`from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
 collection_name="{collection_name}",
 strict_mode_config=models.StrictModeConfig(enabled=True, upsert_max_batchsize=1000),
)
`

`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.createCollection("{collection_name}", {
 strict_mode_config: {
 enabled: true,
 upsert_max_batchsize: 1000,
 },
});
`

`use qdrant_client::Qdrant;
use qdrant_client::qdrant::{CreateCollectionBuilder, StrictModeConfigBuilder};

let client = Qdrant::from_url("http://localhost:6334").build()?;

client
 .create_collection(
 CreateCollectionBuilder::new("{collection_name}")
 .strict_mode_config(StrictModeConfigBuilder::default().enabled(true).upsert_max_batchsize(1000)),
 )
 .await?;
`

`import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Collections.CreateCollection;
import io.qdrant.client.grpc.Collections.StrictModeConfig;

QdrantClient client =
 new QdrantClient(QdrantGrpcClient.newBuilder("localhost", 6334, false).build());

client
 .createCollectionAsync(
 CreateCollection.newBuilder()
 .setCollectionName("{collection_name}")
 .setStrictModeConfig(
 StrictModeConfig.newBuilder().setEnabled(true).setUpsertMaxBatchsize(1000).build())
 .build())
 .get();
`

`using Qdrant.Client;
using Qdrant.Client.Grpc;

var client = new QdrantClient("localhost", 6334);

await client.CreateCollectionAsync(
 collectionName: "{collection_name}",
 strictModeConfig: new StrictModeConfig { Enabled = true, UpsertMaxBatchsize = 1000 }
);
`

`import (
 "context"

 "github.com/qdrant/go-client/qdrant"
)

client, err := qdrant.NewClient(&qdrant.Config{
 Host: "localhost",
 Port: 6334,
})

client.CreateCollection(context.Background(), &qdrant.CreateCollection{
 CollectionName: "{collection_name}",
 StrictModeConfig: &qdrant.StrictModeConfig{
 Enabled: qdrant.PtrOf(true),
 UpsertMaxBatchsize: qdrant.PtrOf(uint64(1000)),
 },
})
`
### Maximum Batch Size When Searching


Sending very large search batches can create internal congestion.

Setting `search_max_batchsize` caps the maximum number of searches in a single batch request.

`PUT /collections/{collection_name}
{
 "strict_mode_config": {
 "enabled": true,
 "search_max_batchsize": 1000
 }
}
`

`curl -X PUT http://localhost:6333/collections/{collection_name} \
 -H 'Content-Type: application/json' \
 --data-raw '{
 "strict_mode_config": {
 "enabled": true,
 "search_max_batchsize": 1000
 }
 }'
`

`from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
 collection_name="{collection_name}",
 strict_mode_config=models.StrictModeConfig(enabled=True, search_max_batchsize=1000),
)
`

`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.createCollection("{collection_name}", {
 strict_mode_config: {
 enabled: true,
 search_max_batchsize: 1000,
 },
});
`

`use qdrant_client::Qdrant;
use qdrant_client::qdrant::{CreateCollectionBuilder, StrictModeConfigBuilder};

let client = Qdrant::from_url("http://localhost:6334").build()?;

client
 .create_collection(
 CreateCollectionBuilder::new("{collection_name}")
 .strict_mode_config(StrictModeConfigBuilder::default().enabled(true).search_max_batchsize(1000u64)),
 )
 .await?;
`

`import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Collections.CreateCollection;
import io.qdrant.client.grpc.Collections.StrictModeConfig;

QdrantClient client =
 new QdrantClient(QdrantGrpcClient.newBuilder("localhost", 6334, false).build());

client
 .createCollectionAsync(
 CreateCollection.newBuilder()
 .setCollectionName("{collection_name}")
 .setStrictModeConfig(
 StrictModeConfig.newBuilder().setEnabled(true).setSearchMaxBatchsize(1000).build())
 .build())
 .get();
`

`using Qdrant.Client;
using Qdrant.Client.Grpc;

var client = new QdrantClient("localhost", 6334);

await client.CreateCollectionAsync(
 collectionName: "{collection_name}",
 strictModeConfig: new StrictModeConfig { Enabled = true, SearchMaxBatchsize = 1000 }
);
`

`import (
 "context"

 "github.com/qdrant/go-client/qdrant"
)

client, err := qdrant.NewClient(&qdrant.Config{
 Host: "localhost",
 Port: 6334,
})

client.CreateCollection(context.Background(), &qdrant.CreateCollection{
 CollectionName: "{collection_name}",
 StrictModeConfig: &qdrant.StrictModeConfig{
 Enabled: qdrant.PtrOf(true),
 SearchMaxBatchsize: qdrant.PtrOf(uint64(1000)),
 },
})
`
### Maximum Collection Storage Size


It is possible to set the maximum size of a collection in terms of vectors and/or payload storage size.

Setting `max_collection_vector_size_bytes` and/or `max_collection_payload_size_bytes` caps the maximum byte size of a collection.

`PUT /collections/{collection_name}
{
 "strict_mode_config": {
 "enabled": true,
 "max_collection_vector_size_bytes": 1000000,
 "max_collection_payload_size_bytes": 1000000
 }
}
`

`curl -X PUT http://localhost:6333/collections/{collection_name} \
 -H 'Content-Type: application/json' \
 --data-raw '{
 "strict_mode_config": {
 "enabled":" true,
 "max_collection_vector_size_bytes": 100000,
 "max_collection_payload_size_bytes": 100000
 }
 }'
`

`from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
 collection_name="{collection_name}",
 strict_mode_config=models.StrictModeConfig(enabled=True, max_collection_vector_size_bytes=1000000, max_collection_payload_size_bytes=1000000),
)
`

`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.createCollection("{collection_name}", {
 strict_mode_config: {
 enabled: true,
 max_collection_vector_size_bytes: 1000000,
 max_collection_payload_size_bytes: 1000000,
 },
});
`

`use qdrant_client::Qdrant;
use qdrant_client::qdrant::{CreateCollectionBuilder, StrictModeConfigBuilder};

let client = Qdrant::from_url("http://localhost:6334").build()?;

client
 .create_collection(
 CreateCollectionBuilder::new("{collection_name}")
 .strict_mode_config(StrictModeConfigBuilder::default().enabled(true).max_collection_vector_size_bytes(1000000).max_collection_payload_size_bytes(1000000)),
 )
 .await?;
`

`import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Collections.CreateCollection;
import io.qdrant.client.grpc.Collections.StrictModeConfig;

QdrantClient client =
 new QdrantClient(QdrantGrpcClient.newBuilder("localhost", 6334, false).build());

client
 .createCollectionAsync(
 CreateCollection.newBuilder()
 .setCollectionName("{collection_name}")
 .setStrictModeConfig(
 StrictModeConfig.newBuilder().setEnabled(true).setMaxCollectionVectorSizeBytes(1000000).setMaxCollectionPayloadSizeBytes(1000000).build())
 .build())
 .get();
`

`using Qdrant.Client;
using Qdrant.Client.Grpc;

var client = new QdrantClient("localhost", 6334);

await client.CreateCollectionAsync(
 collectionName: "{collection_name}",
 strictModeConfig: new StrictModeConfig { Enabled = true, MaxCollectionVectorSizeBytes = 1000000, MaxCollectionPayloadSizeBytes = 1000000 }
);
`

`import (
 "context"

 "github.com/qdrant/go-client/qdrant"
)

client, err := qdrant.NewClient(&qdrant.Config{
 Host: "localhost",
 Port: 6334,
})

client.CreateCollection(context.Background(), &qdrant.CreateCollection{
 CollectionName: "{collection_name}",
 StrictModeConfig: &qdrant.StrictModeConfig{
 Enabled: qdrant.PtrOf(true),
 MaxCollectionVectorSizeBytes: qdrant.PtrOf(uint64(1000000)),
 MaxCollectionPayloadSizeBytes: qdrant.PtrOf(uint64(1000000)),
 },
})
`
### Maximum Resident Memory Usage


When a node is under memory pressure, new write operations can destabilize the cluster.

Setting `max_resident_memory_percent` rejects memory-consuming write operations (such as upsert and set payload) when process resident memory exceeds the given percentage of total system memory. Delete operations are not affected. Accepts values in the range 1–100.

`PUT /collections/{collection_name}
{
 "strict_mode_config": {
 "enabled": true,
 "max_resident_memory_percent": 90
 }
}
`

`curl -X PUT http://localhost:6333/collections/{collection_name} \
 -H 'Content-Type: application/json' \
 --data-raw '{
 "strict_mode_config": {
 "enabled": true,
 "max_resident_memory_percent": 90
 }
 }'
`

`from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
 collection_name="{collection_name}",
 strict_mode_config=models.StrictModeConfig(enabled=True, max_resident_memory_percent=90),
)
`

`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.createCollection("{collection_name}", {
 strict_mode_config: {
 enabled: true,
 max_resident_memory_percent: 90,
 },
});
`

`use qdrant_client::Qdrant;
use qdrant_client::qdrant::{CreateCollectionBuilder, StrictModeConfigBuilder};

let client = Qdrant::from_url("http://localhost:6334").build()?;

client
 .create_collection(
 CreateCollectionBuilder::new("{collection_name}")
 .strict_mode_config(StrictModeConfigBuilder::default().enabled(true).max_resident_memory_percent(90u32)),
 )
 .await?;
`

`import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Collections.CreateCollection;
import io.qdrant.client.grpc.Collections.StrictModeConfig;

QdrantClient client =
 new QdrantClient(QdrantGrpcClient.newBuilder("localhost", 6334, false).build());

client
 .createCollectionAsync(
 CreateCollection.newBuilder()
 .setCollectionName("{collection_name}")
 .setStrictModeConfig(
 StrictModeConfig.newBuilder().setEnabled(true).setMaxResidentMemoryPercent(90).build())
 .build())
 .get();
`

`using Qdrant.Client;
using Qdrant.Client.Grpc;

var client = new QdrantClient("localhost", 6334);

await client.CreateCollectionAsync(
 collectionName: "{collection_name}",
 strictModeConfig: new StrictModeConfig { Enabled = true, MaxResidentMemoryPercent = 90 }
);
`

`import (
 "context"

 "github.com/qdrant/go-client/qdrant"
)

client, err := qdrant.NewClient(&qdrant.Config{
 Host: "localhost",
 Port: 6334,
})

client.CreateCollection(context.Background(), &qdrant.CreateCollection{
 CollectionName: "{collection_name}",
 StrictModeConfig: &qdrant.StrictModeConfig{
 Enabled: qdrant.PtrOf(true),
 MaxResidentMemoryPercent: qdrant.PtrOf(uint32(90)),
 },
})
`
### Maximum Points Count


Setting `max_points_count` caps the maximum number of points for a collection.

`PUT /collections/{collection_name}
{
 "strict_mode_config": {
 "enabled": true,
 "max_points_count": 1000
 }
}
`

`curl -X PUT http://localhost:6333/collections/{collection_name} \
 -H 'Content-Type: application/json' \
 --data-raw '{
 "strict_mode_config": {
 "enabled":" true,
 "max_points_count": 1000
 }
 }'
`

`from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
 collection_name="{collection_name}",
 strict_mode_config=models.StrictModeConfig(enabled=True, max_points_count=1000),
)
`

`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.createCollection("{collection_name}", {
 strict_mode_config: {
 enabled: true,
 max_points_count: 1000,
 },
});
`

`use qdrant_client::Qdrant;
use qdrant_client::qdrant::{CreateCollectionBuilder, StrictModeConfigBuilder};

let client = Qdrant::from_url("http://localhost:6334").build()?;

client
 .create_collection(
 CreateCollectionBuilder::new("{collection_name}")
 .strict_mode_config(StrictModeConfigBuilder::default().enabled(true).max_points_count(1000)),
 )
 .await?;
`

`import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Collections.CreateCollection;
import io.qdrant.client.grpc.Collections.StrictModeConfig;

QdrantClient client =
 new QdrantClient(QdrantGrpcClient.newBuilder("localhost", 6334, false).build());

client
 .createCollectionAsync(
 CreateCollection.newBuilder()
 .setCollectionName("{collection_name}")
 .setStrictModeConfig(
 StrictModeConfig.newBuilder().setEnabled(true).setMaxPointsCount(1000).build())
 .build())
 .get();
`

`using Qdrant.Client;
using Qdrant.Client.Grpc;

var client = new QdrantClient("localhost", 6334);

await client.CreateCollectionAsync(
 collectionName: "{collection_name}",
 strictModeConfig: new StrictModeConfig { Enabled = true, MaxPointsCount = 1000 }
);
`

`import (
 "context"

 "github.com/qdrant/go-client/qdrant"
)

client, err := qdrant.NewClient(&qdrant.Config{
 Host: "localhost",
 Port: 6334,
})

client.CreateCollection(context.Background(), &qdrant.CreateCollection{
 CollectionName: "{collection_name}",
 StrictModeConfig: &qdrant.StrictModeConfig{
 Enabled: qdrant.PtrOf(true),
 MaxPointsCount: qdrant.PtrOf(uint64(1000)),
 },
})
`
### Rate Limiting


An extremely high rate of incoming requests can have a negative impact on the latency.

Setting ead_rate_limit` and/or `write_rate_limit` to cap the maximum number of operations per minute per replica.

When exceeding the maximum number of operations, the client will receive an HTTP 429 error code with a suggested delay before retrying.

`PUT /collections/{collection_name}
{
 "strict_mode_config": {
 "enabled": true,
 "read_rate_limit": 1000,
 "write_rate_limit": 100,
 }
}
`

`curl -X PUT http://localhost:6333/collections/{collection_name} \
 -H 'Content-Type: application/json' \
 --data-raw '{
 "strict_mode_config": {
 "enabled":" true,
 "read_rate_limit": 1000,
 "write_rate_limit": 100,
 }
 }'
`

`from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
 collection_name="{collection_name}",
 strict_mode_config=models.StrictModeConfig(enabled=True, read_rate_limit=1000, write_rate_limit=1000,),
)
`

`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.createCollection("{collection_name}", {
 strict_mode_config: {
 enabled: true,
 read_rate_limit: 1000,
 write_rate_limit: 100,
 },
});
`

`use qdrant_client::Qdrant;
use qdrant_client::qdrant::{CreateCollectionBuilder, StrictModeConfigBuilder};

let client = Qdrant::from_url("http://localhost:6334").build()?;

client
 .create_collection(
 CreateCollectionBuilder::new("{collection_name}")
 .strict_mode_config(StrictModeConfigBuilder::default().enabled(true).read_rate_limit(1000).write_rate_limit(100)),
 )
 .await?;
`

`import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Collections.CreateCollection;
import io.qdrant.client.grpc.Collections.StrictModeConfig;

QdrantClient client =
 new QdrantClient(QdrantGrpcClient.newBuilder("localhost", 6334, false).build());

client
 .createCollectionAsync(
 CreateCollection.newBuilder()
 .setCollectionName("{collection_name}")
 .setStrictModeConfig(
 StrictModeConfig.newBuilder().setEnabled(true).setReadRateLimit(1000).setWriteRateLimit(100).build())
 .build())
 .get();
`

`using Qdrant.Client;
using Qdrant.Client.Grpc;

var client = new QdrantClient("localhost", 6334);

await client.CreateCollectionAsync(
 collectionName: "{collection_name}",
 strictModeConfig: new StrictModeConfig { Enabled = true, ReadRateLimit = 1000, WriteRateLimit = 100}
);
`

`import (
 "context"

 "github.com/qdrant/go-client/qdrant"
)

client, err := qdrant.NewClient(&qdrant.Config{
 Host: "localhost",
 Port: 6334,
})

client.CreateCollection(context.Background(), &qdrant.CreateCollection{
 CollectionName: "{collection_name}",
 StrictModeConfig: &qdrant.StrictModeConfig{
 Enabled: qdrant.PtrOf(true),
 ReadRateLimit: qdrant.PtrOf(uint32(1000)),
 WriteRateLimit: qdrant.PtrOf(uint32(100)),
 },
})
`
### Maximum Vectors per Multivector


A multivector with many vectors per point is expensive to store, index and query.

Setting `multivector_config` caps the maximum number of vectors per multivector for each named vector.

`PUT /collections/{collection_name}
{
 "strict_mode_config": {
 "enabled": true,
 "multivector_config": {
 "{vector_name}": {
 "max_vectors": 10
 }
 }
 }
}
`

`curl -X PUT http://localhost:6333/collections/{collection_name} \
 -H 'Content-Type: application/json' \
 --data-raw '{
 "strict_mode_config": {
 "enabled": true,
 "multivector_config": {
 "{vector_name}": {
 "max_vectors": 10
 }
 }
 }
 }'
`

`from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
 collection_name="{collection_name}",
 strict_mode_config=models.StrictModeConfig(
 enabled=True,
 multivector_config={"{vector_name}": models.StrictModeMultivector(max_vectors=10)},
 ),
)
`

`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.createCollection("{collection_name}", {
 strict_mode_config: {
 enabled: true,
 multivector_config: {
 "{vector_name}": {
 max_vectors: 10,
 },
 },
 },
});
`

`use std::collections::HashMap;

use qdrant_client::Qdrant;
use qdrant_client::qdrant::{
 CreateCollectionBuilder, StrictModeConfigBuilder, StrictModeMultivector,
 StrictModeMultivectorConfig,
};

let client = Qdrant::from_url("http://localhost:6334").build()?;

client
 .create_collection(
 CreateCollectionBuilder::new("{collection_name}").strict_mode_config(
 StrictModeConfigBuilder::default()
 .enabled(true)
 .multivector_config(StrictModeMultivectorConfig {
 multivector_config: HashMap::from([(
 "{vector_name}".to_string(),
 StrictModeMultivector {
 max_vectors: Some(10),
 },
 )]),
 }),
 ),
 )
 .await?;
`

`import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Collections.CreateCollection;
import io.qdrant.client.grpc.Collections.StrictModeConfig;
import io.qdrant.client.grpc.Collections.StrictModeMultivector;
import io.qdrant.client.grpc.Collections.StrictModeMultivectorConfig;

QdrantClient client =
 new QdrantClient(QdrantGrpcClient.newBuilder("localhost", 6334, false).build());

client
 .createCollectionAsync(
 CreateCollection.newBuilder()
 .setCollectionName("{collection_name}")
 .setStrictModeConfig(
 StrictModeConfig.newBuilder()
 .setEnabled(true)
 .setMultivectorConfig(
 StrictModeMultivectorConfig.newBuilder()
 .putMultivectorConfig("{vector_name}", StrictModeMultivector.newBuilder().setMaxVectors(10).build())
 .build())
 .build())
 .build())
 .get();
`

`using Qdrant.Client;
using Qdrant.Client.Grpc;

var client = new QdrantClient("localhost", 6334);

await client.CreateCollectionAsync(
 collectionName: "{collection_name}",
 strictModeConfig: new StrictModeConfig
 {
 Enabled = true,
 MultivectorConfig = new StrictModeMultivectorConfig
 {
 MultivectorConfig = { ["{vector_name}"] = new StrictModeMultivector { MaxVectors = 10 } }
 }
 }
);
`

`import (
 "context"

 "github.com/qdrant/go-client/qdrant"
)

client, err := qdrant.NewClient(&qdrant.Config{
 Host: "localhost",
 Port: 6334,
})

client.CreateCollection(context.Background(), &qdrant.CreateCollection{
 CollectionName: "{collection_name}",
 StrictModeConfig: &qdrant.StrictModeConfig{
 Enabled: qdrant.PtrOf(true),
 MultivectorConfig: &qdrant.StrictModeMultivectorConfig{
 MultivectorConfig: map[string]*qdrant.StrictModeMultivector{
 "{vector_name}": {MaxVectors: qdrant.PtrOf(uint64(10))},
 },
 },
 },
})
`
### Maximum Sparse Vector Length


Long sparse vectors increase memory usage and slow down filtering.

Setting `sparse_config` caps the maximum length of sparse vectors for each named vector.

`PUT /collections/{collection_name}
{
 "strict_mode_config": {
 "enabled": true,
 "sparse_config": {
 "{vector_name}": {
 "max_length": 1000
 }
 }
 }
}
`

`curl -X PUT http://localhost:6333/collections/{collection_name} \
 -H 'Content-Type: application/json' \
 --data-raw '{
 "strict_mode_config": {
 "enabled": true,
 "sparse_config": {
 "{vector_name}": {
 "max_length": 1000
 }
 }
 }
 }'
`

`from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
 collection_name="{collection_name}",
 strict_mode_config=models.StrictModeConfig(
 enabled=True,
 sparse_config={"{vector_name}": models.StrictModeSparse(max_length=1000)},
 ),
)
`

`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.createCollection("{collection_name}", {
 strict_mode_config: {
 enabled: true,
 sparse_config: {
 "{vector_name}": {
 max_length: 1000,
 },
 },
 },
});
`

`use std::collections::HashMap;

use qdrant_client::Qdrant;
use qdrant_client::qdrant::{
 CreateCollectionBuilder, StrictModeConfigBuilder, StrictModeSparse, StrictModeSparseConfig,
};

let client = Qdrant::from_url("http://localhost:6334").build()?;

client
 .create_collection(
 CreateCollectionBuilder::new("{collection_name}").strict_mode_config(
 StrictModeConfigBuilder::default()
 .enabled(true)
 .sparse_config(StrictModeSparseConfig {
 sparse_config: HashMap::from([(
 "{vector_name}".to_string(),
 StrictModeSparse {
 max_length: Some(1000),
 },
 )]),
 }),
 ),
 )
 .await?;
`

`import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Collections.CreateCollection;
import io.qdrant.client.grpc.Collections.StrictModeConfig;
import io.qdrant.client.grpc.Collections.StrictModeSparse;
import io.qdrant.client.grpc.Collections.StrictModeSparseConfig;

QdrantClient client =
 new QdrantClient(QdrantGrpcClient.newBuilder("localhost", 6334, false).build());

client
 .createCollectionAsync(
 CreateCollection.newBuilder()
 .setCollectionName("{collection_name}")
 .setStrictModeConfig(
 StrictModeConfig.newBuilder()
 .setEnabled(true)
 .setSparseConfig(
 StrictModeSparseConfig.newBuilder()
 .putSparseConfig("{vector_name}", StrictModeSparse.newBuilder().setMaxLength(1000).build())
 .build())
 .build())
 .build())
 .get();
`

`using Qdrant.Client;
using Qdrant.Client.Grpc;

var client = new QdrantClient("localhost", 6334);

await client.CreateCollectionAsync(
 collectionName: "{collection_name}",
 strictModeConfig: new StrictModeConfig
 {
 Enabled = true,
 SparseConfig = new StrictModeSparseConfig
 {
 SparseConfig = { ["{vector_name}"] = new StrictModeSparse { MaxLength = 1000 } }
 }
 }
);
`

`import (
 "context"

 "github.com/qdrant/go-client/qdrant"
)

client, err := qdrant.NewClient(&qdrant.Config{
 Host: "localhost",
 Port: 6334,
})

client.CreateCollection(context.Background(), &qdrant.CreateCollection{
 CollectionName: "{collection_name}",
 StrictModeConfig: &qdrant.StrictModeConfig{
 Enabled: qdrant.PtrOf(true),
 SparseConfig: &qdrant.StrictModeSparseConfig{
 SparseConfig: map[string]*qdrant.StrictModeSparse{
 "{vector_name}": {MaxLength: qdrant.PtrOf(uint64(1000))},
 },
 },
 },
})
`
##### Was this page useful?


Yes


No

Thank you for your feedback! 🙏

We are sorry to hear that. 😔 You can edit this page on GitHub, or create a GitHub issue.


Create an issue
