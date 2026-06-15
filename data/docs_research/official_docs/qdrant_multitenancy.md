<!-- source: Qdrant Multitenancy -->
<!-- cleaned: nav-bar removed -->

# Configure Multitenancy


How many collections should you create? In most cases, a single collection per embedding model with payload-based partitioning for different tenants and use cases. This approach is called multitenancy. It is efficient for most users, but requires additional configuration. This document will show you how to set it up.

When should you create multiple collections? When you have a limited number of users and you need isolation. This approach is flexible, but it may be more costly, since creating numerous collections may result in resource overhead. Also, you need to ensure that they do not affect each other in any way, including performance-wise.

## Partition by payload


When an instance is shared between multiple users, you may need to partition vectors by user. This is done so that each user can only access their own vectors and can’t see the vectors of other users.

`PUT /collections/{collection_name}/points
{
 "points": [
 {
 "id": 1,
 "payload": {"group_id": "user_1"},
 "vector": [0.9, 0.1, 0.1]
 },
 {
 "id": 2,
 "payload": {"group_id": "user_1"},
 "vector": [0.1, 0.9, 0.1]
 },
 {
 "id": 3,
 "payload": {"group_id": "user_2"},
 "vector": [0.1, 0.1, 0.9]
 },
 ]
}
`
```


`client.upsert(
 collection_name="{collection_name}",
 points=[
 models.PointStruct(
 id=1,
 payload={"group_id": "user_1"},
 vector=[0.9, 0.1, 0.1],
 ),
 models.PointStruct(
 id=2,
 payload={"group_id": "user_1"},
 vector=[0.1, 0.9, 0.1],
 ),
 models.PointStruct(
 id=3,
 payload={"group_id": "user_2"},
 vector=[0.1, 0.1, 0.9],
 ),
 ],
)
`
```


`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.upsert("{collection_name}", {
 points: [
 {
 id: 1,
 payload: { group_id: "user_1" },
 vector: [0.9, 0.1, 0.1],
 },
 {
 id: 2,
 payload: { group_id: "user_1" },
 vector: [0.1, 0.9, 0.1],
 },
 {
 id: 3,
 payload: { group_id: "user_2" },
 vector: [0.1, 0.1, 0.9],
 },
 ],
});
`
```


`use qdrant_client::qdrant::{PointStruct, UpsertPointsBuilder};
use qdrant_client::Qdrant;

let client = Qdrant::from_url("http://localhost:6334").build()?;

client
 .upsert_points(UpsertPointsBuilder::new(
 "{collection_name}",
 vec![
 PointStruct::new(1, vec![0.9, 0.1, 0.1], [("group_id", "user_1".into())]),
 PointStruct::new(2, vec![0.1, 0.9, 0.1], [("group_id", "user_1".into())]),
 PointStruct::new(3, vec![0.1, 0.1, 0.9], [("group_id", "user_2".into())]),
 ],
 ))
 .await?;
`
```


`import static io.qdrant.client.PointIdFactory.id;
import static io.qdrant.client.ValueFactory.value;
import static io.qdrant.client.VectorsFactory.vectors;

import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Points.PointStruct;
import java.util.List;
import java.util.Map;

QdrantClient client =
 new QdrantClient(QdrantGrpcClient.newBuilder("localhost", 6334, false).build());

client
 .upsertAsync(
 "{collection_name}",
 List.of(
 PointStruct.newBuilder()
 .setId(id(1))
 .setVectors(vectors(0.9f, 0.1f, 0.1f))
 .putAllPayload(Map.of("group_id", value("user_1")))
 .build(),
 PointStruct.newBuilder()
 .setId(id(2))
 .setVectors(vectors(0.1f, 0.9f, 0.1f))
 .putAllPayload(Map.of("group_id", value("user_1")))
 .build(),
 PointStruct.newBuilder()
 .setId(id(3))
 .setVectors(vectors(0.1f, 0.1f, 0.9f))
 .putAllPayload(Map.of("group_id", value("user_2")))
 .build()))
 .get();
`
```


`using Qdrant.Client;
using Qdrant.Client.Grpc;

var client = new QdrantClient("localhost", 6334);

await client.UpsertAsync(
 collectionName: "{collection_name}",
 points: new List<PointStruct>
 {
 new()
 {
 Id = 1,
 Vectors = new[] { 0.9f, 0.1f, 0.1f },
 Payload = { ["group_id"] = "user_1" }
 },
 new()
 {
 Id = 2,
 Vectors = new[] { 0.1f, 0.9f, 0.1f },
 Payload = { ["group_id"] = "user_1" }
 },
 new()
 {
 Id = 3,
 Vectors = new[] { 0.1f, 0.1f, 0.9f },
 Payload = { ["group_id"] = "user_2" }
 }
 }
);
`
```


`import (
 "context"

 "github.com/qdrant/go-client/qdrant"
)

client, err := qdrant.NewClient(&qdrant.Config{
 Host: "localhost",
 Port: 6334,
})

client.Upsert(context.Background(), &qdrant.UpsertPoints{
 CollectionName: "{collection_name}",
 Points: []*qdrant.PointStruct{
 {
 Id: qdrant.NewIDNum(1),
 Vectors: qdrant.NewVectors(0.9, 0.1, 0.1),
 Payload: qdrant.NewValueMap(map[string]any{"group_id": "user_1"}),
 },
 {
 Id: qdrant.NewIDNum(2),
 Vectors: qdrant.NewVectors(0.1, 0.9, 0.1),
 Payload: qdrant.NewValueMap(map[string]any{"group_id": "user_1"}),
 },
 {
 Id: qdrant.NewIDNum(3),
 Vectors: qdrant.NewVectors(0.1, 0.1, 0.9),
 Payload: qdrant.NewValueMap(map[string]any{"group_id": "user_2"}),
 },
 },
})
`
```

- Use a filter along with `group_id` to filter vectors for each user.

`POST /collections/{collection_name}/points/query
{
 "query": [0.1, 0.1, 0.9],
 "filter": {
 "must": [
 {
 "key": "group_id",
 "match": {
 "value": "user_1"
 }
 }
 ]
 },
 "limit": 10
}
`
```


`from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.query_points(
 collection_name="{collection_name}",
 query=[0.1, 0.1, 0.9],
 query_filter=models.Filter(
 must=[
 models.FieldCondition(
 key="group_id",
 match=models.MatchValue(
 value="user_1",
 ),
 )
 ]
 ),
 limit=10,
)
`
```


`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.query("{collection_name}", {
 query: [0.1, 0.1, 0.9],
 filter: {
 must: [{ key: "group_id", match: { value: "user_1" } }],
 },
 limit: 10,
});
`
```


`use qdrant_client::qdrant::{Condition, Filter, QueryPointsBuilder};
use qdrant_client::Qdrant;

let client = Qdrant::from_url("http://localhost:6334").build()?;

client
 .query(
 QueryPointsBuilder::new("{collection_name}")
 .query(vec![0.1, 0.1, 0.9])
 .limit(10)
 .filter(Filter::must([Condition::matches(
 "group_id",
 "user_1".to_string(),
 )])),
 )
 .await?;
`
```


`import static io.qdrant.client.ConditionFactory.matchKeyword;
import static io.qdrant.client.QueryFactory.nearest;

import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Common.Filter;
import io.qdrant.client.grpc.Points.QueryPoints;
import java.util.List;

QdrantClient client =
 new QdrantClient(QdrantGrpcClient.newBuilder("localhost", 6334, false).build());

client.queryAsync(
 QueryPoints.newBuilder()
 .setCollectionName("{collection_name}")
 .setFilter(
 Filter.newBuilder().addMust(matchKeyword("group_id", "user_1")).build())
 .setQuery(nearest(0.1f, 0.1f, 0.9f))
 .setLimit(10)
 .build())
 .get();
`
```


`using Qdrant.Client;
using Qdrant.Client.Grpc;
using static Qdrant.Client.Grpc.Conditions;

var client = new QdrantClient("localhost", 6334);

await client.QueryAsync(
 collectionName: "{collection_name}",
 query: new float[] { 0.1f, 0.1f, 0.9f },
 filter: MatchKeyword("group_id", "user_1"),
 limit: 10
);
`
```


`import (
 "context"

 "github.com/qdrant/go-client/qdrant"
)

client, err := qdrant.NewClient(&qdrant.Config{
 Host: "localhost",
 Port: 6334,
})

client.Query(context.Background(), &qdrant.QueryPoints{
 CollectionName: "{collection_name}",
 Query: qdrant.NewQuery(0.1, 0.1, 0.9),
 Filter: &qdrant.Filter{
 Must: []*qdrant.Condition{
 qdrant.NewMatch("group_id", "user_1"),
 },
 },
})
`
```


## Calibrate performance


The speed of indexation may become a bottleneck in this case, as each user’s vector will be indexed into the same collection. To avoid this bottleneck, consider bypassing the construction of a global vector index for the entire collection and building it only for individual groups instead.

By adopting this strategy, Qdrant will index vectors for each user independently, significantly accelerating the process.

To implement this approach, you should:
- Set `payload_m` in the HNSW configuration to a non-zero value, such as 16.
- Set `m` in hnsw config to 0. This will disable building global index for the whole collection.

`PUT /collections/{collection_name}
{
 "vectors": {
 "size": 768,
 "distance": "Cosine"
 },
 "hnsw_config": {
 "payload_m": 16,
 "m": 0
 }
}
`
```


`from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
 collection_name="{collection_name}",
 vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE),
 hnsw_config=models.HnswConfigDiff(
 payload_m=16,
 m=0,
 ),
)
`
```


`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.createCollection("{collection_name}", {
 vectors: {
 size: 768,
 distance: "Cosine",
 },
 hnsw_config: {
 payload_m: 16,
 m: 0,
 },
});
`
```


`use qdrant_client::qdrant::{
 CreateCollectionBuilder, Distance, HnswConfigDiffBuilder, VectorParamsBuilder,
};
use qdrant_client::Qdrant;

let client = Qdrant::from_url("http://localhost:6334").build()?;

client
 .create_collection(
 CreateCollectionBuilder::new("{collection_name}")
 .vectors_config(VectorParamsBuilder::new(768, Distance::Cosine))
 .hnsw_config(HnswConfigDiffBuilder::default().payload_m(16).m(0)),
 )
 .await?;
`
```


`import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Collections.CreateCollection;
import io.qdrant.client.grpc.Collections.Distance;
import io.qdrant.client.grpc.Collections.HnswConfigDiff;
import io.qdrant.client.grpc.Collections.VectorParams;
import io.qdrant.client.grpc.Collections.VectorsConfig;

QdrantClient client =
 new QdrantClient(QdrantGrpcClient.newBuilder("localhost", 6334, false).build());

client
 .createCollectionAsync(
 CreateCollection.newBuilder()
 .setCollectionName("{collection_name}")
 .setVectorsConfig(
 VectorsConfig.newBuilder()
 .setParams(
 VectorParams.newBuilder()
 .setSize(768)
 .setDistance(Distance.Cosine)
 .build())
 .build())
 .setHnswConfig(HnswConfigDiff.newBuilder().setPayloadM(16).setM(0).build())
 .build())
 .get();
`
```


`using Qdrant.Client;
using Qdrant.Client.Grpc;

var client = new QdrantClient("localhost", 6334);

await client.CreateCollectionAsync(
 collectionName: "{collection_name}",
 vectorsConfig: new VectorParams { Size = 768, Distance = Distance.Cosine },
 hnswConfig: new HnswConfigDiff { PayloadM = 16, M = 0 }
);
`
```


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
 VectorsConfig: qdrant.NewVectorsConfig(&qdrant.VectorParams{
 Size: 768,
 Distance: qdrant.Distance_Cosine,
 }),
 HnswConfig: &qdrant.HnswConfigDiff{
 PayloadM: qdrant.PtrOf(uint64(16)),
 M: qdrant.PtrOf(uint64(0)),
 },
})
`
```

- Create keyword payload index for `group_id` field.

`PUT /collections/{collection_name}/index
{
 "field_name": "group_id",
 "field_schema": {
 "type": "keyword",
 "is_tenant": true
 }
}
`
```


`client.create_payload_index(
 collection_name="{collection_name}",
 field_name="group_id",
 field_schema=models.KeywordIndexParams(
 type=models.KeywordIndexType.KEYWORD,
 is_tenant=True,
 ),
)
`
```


`client.createPayloadIndex("{collection_name}", {
 field_name: "group_id",
 field_schema: {
 type: "keyword",
 is_tenant: true,
 },
});
`
```


`use qdrant_client::qdrant::{
 CreateFieldIndexCollectionBuilder,
 KeywordIndexParamsBuilder,
 FieldType
};
use qdrant_client::Qdrant;

let client = Qdrant::from_url("http://localhost:6334").build()?;

client.create_field_index(
 CreateFieldIndexCollectionBuilder::new(
 "{collection_name}",
 "group_id",
 FieldType::Keyword,
 ).field_index_params(
 KeywordIndexParamsBuilder::default()
 .is_tenant(true)
 )
 ).await?;
`
```


`import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Collections.KeywordIndexParams;
import io.qdrant.client.grpc.Collections.PayloadIndexParams;
import io.qdrant.client.grpc.Collections.PayloadSchemaType;

QdrantClient client =
 new QdrantClient(QdrantGrpcClient.newBuilder("localhost", 6334, false).build());

client
 .createPayloadIndexAsync(
 "{collection_name}",
 "group_id",
 PayloadSchemaType.Keyword,
 PayloadIndexParams.newBuilder()
 .setKeywordIndexParams(
 KeywordIndexParams.newBuilder()
 .setIsTenant(true)
 .build())
 .build(),
 null,
 null,
 null)
 .get();
`
```


`using Qdrant.Client;
using Qdrant.Client.Grpc;

var client = new QdrantClient("localhost", 6334);

await client.CreatePayloadIndexAsync(
 collectionName: "{collection_name}",
 fieldName: "group_id",
 schemaType: PayloadSchemaType.Keyword,
 indexParams: new PayloadIndexParams
 {
 KeywordIndexParams = new KeywordIndexParams
 {
 IsTenant = true
 }
 }
);
`
```


`import (
 "context"

 "github.com/qdrant/go-client/qdrant"
)

client, err := qdrant.NewClient(&qdrant.Config{
 Host: "localhost",
 Port: 6334,
})

client.CreateFieldIndex(context.Background(), &qdrant.CreateFieldIndexCollection{
 CollectionName: "{collection_name}",
 FieldName: "group_id",
 FieldType: qdrant.FieldType_FieldTypeKeyword.Enum(),
 FieldIndexParams: qdrant.NewPayloadIndexParams(
 &qdrant.KeywordIndexParams{
 IsTenant: qdrant.PtrOf(true),
 }),
})
`
```


`is_tenant=true` parameter is optional, but specifying it provides storage with additional information about the usage patterns the collection is going to use.
When specified, storage structure will be organized in a way to co-locate vectors of the same tenant together, which can significantly improve performance by utilizing sequential reads during queries.

Grouping tenants together by tenant ID, if `is_tenant=true` is used

### Limitations


One downside to this approach is that global requests (without the `group_id` filter) will be slower since they will necessitate scanning all groups to identify the nearest neighbors.

## Tiered multitenancy


In some real-world applications, tenants might not be equally distributed. For example, a SaaS application might have a few large customers and many small ones.
Large tenants might require extended resources and isolation, while small tenants should not create too much overhead.

One solution to this problem might be to introduce application-level logic to separate tenants into different collections based on their size or resource requirements.
There is, however, a downside to this approach: we might not know in advance which tenants will be large and which stay small.
In addition, application-level logic increases complexity of the system and requires additional source of truth for tenant placement management.

To address this problem, in v1.16.0 Qdrant provides a built-in mechanism for tiered multitenancy.

With tiered multitenancy, you can implement two levels of tenant isolation within a single collection, keeping small tenants together inside a shared Shard, while isolating large tenants into their own dedicated Shards.
There are 3 components in Qdrant, that allows you to implement tiered multitenancy:
- User-defined Sharding allows you to create named Shards within a collection. It allows to isolate large tenants into their own Shards.
- Fallback shards - a special routing mechanism that allows to route request to either a dedicated Shard (if it exists) or to a shared Fallback Shard. It allows to keep requests unified, without the need to know whether a tenant is dedicated or shared.
- Tenant promotion - a mechanism that allows to move tenants from the shared Fallback Shard to their own dedicated Shard when they grow large enough. This process is based on Qdrant’s internal shard transfer mechanism, which makes promotion completely transparent for the application. Both read and write requests are supported during the promotion process.

Tiered multitenancy with tenant promotion

### Configure tiered multitenancy


To take advantage of tiered multitenancy, you need to create a collection with user-defined (aka `custom`) sharding and create a Fallback Shard in it.

`PUT /collections/{collection_name}
{
 "shard_number": 1,
 "sharding_method": "custom"
 // ... other collection parameters
}
`
```


`from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
 collection_name="{collection_name}",
 shard_number=1,
 sharding_method=models.ShardingMethod.CUSTOM,
 # ... other collection parameters
)
`
```


`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.createCollection("{collection_name}", {
 shard_number: 1,
 sharding_method: "custom",
 // ... other collection parameters
});
`
```


`use qdrant_client::qdrant::{
 CreateCollectionBuilder, Distance, ShardingMethod, VectorParamsBuilder,
};
use qdrant_client::Qdrant;

let client = Qdrant::from_url("http://localhost:6334").build()?;

client
 .create_collection(
 CreateCollectionBuilder::new("{collection_name}")
 .vectors_config(VectorParamsBuilder::new(300, Distance::Cosine))
 .shard_number(1)
 .sharding_method(ShardingMethod::Custom.into()),
 )
 .await?;
`
```


`import static io.qdrant.client.ShardKeyFactory.shardKey;

import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Collections.CreateCollection;
import io.qdrant.client.grpc.Collections.ShardingMethod;

QdrantClient client =
 new QdrantClient(QdrantGrpcClient.newBuilder("localhost", 6334, false).build());

client
 .createCollectionAsync(
 CreateCollection.newBuilder()
 .setCollectionName("{collection_name}")
 // ... other collection parameters
 .setShardNumber(1)
 .setShardingMethod(ShardingMethod.Custom)
 .build())
 .get();
`
```


`using Qdrant.Client;
using Qdrant.Client.Grpc;

var client = new QdrantClient("localhost", 6334);

await client.CreateCollectionAsync(
 collectionName: "{collection_name}",
 // ... other collection parameters
 shardNumber: 1,
 shardingMethod: ShardingMethod.Custom
);
`
```


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
 // ... other collection parameters
 ShardNumber: qdrant.PtrOf(uint32(1)),
 ShardingMethod: qdrant.ShardingMethod_Custom.Enum(),
})
`
```


Start with creating a fallback Shard, which will be used to store small tenants.
Let’s name it `default`.

`PUT /collections/{collection_name}/shards
{
 "shard_key": "default"
}
`
```


`from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.create_shard_key("{collection_name}", "default")
`
```


`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.createShardKey("{collection_name}", {
 shard_key: "default"
});
`
```


`use qdrant_client::qdrant::{
 CreateShardKeyBuilder, CreateShardKeyRequestBuilder
};
use qdrant_client::Qdrant;

let client = Qdrant::from_url("http://localhost:6334").build()?;

client
 .create_shard_key(
 CreateShardKeyRequestBuilder::new("{collection_name}")
 .request(CreateShardKeyBuilder::default().shard_key("default".to_string())),
 )
 .await?;
`
```


`import static io.qdrant.client.ShardKeyFactory.shardKey;

import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Collections.CreateShardKey;
import io.qdrant.client.grpc.Collections.CreateShardKeyRequest;

QdrantClient client =
 new QdrantClient(QdrantGrpcClient.newBuilder("localhost", 6334, false).build());

client.createShardKeyAsync(CreateShardKeyRequest.newBuilder()
 .setCollectionName("{collection_name}")
 .setRequest(CreateShardKey.newBuilder()
 .setShardKey(shardKey("default"))
 .build())
 .build()).get();
`
```


`using Qdrant.Client;
using Qdrant.Client.Grpc;

var client = new QdrantClient("localhost", 6334);

await client.CreateShardKeyAsync(
 "{collection_name}",
 new CreateShardKey { ShardKey = new ShardKey { Keyword = "default", } }
 );
`
```


`import (
 "context"

 "github.com/qdrant/go-client/qdrant"
)

client, err := qdrant.NewClient(&qdrant.Config{
 Host: "localhost",
 Port: 6334,
})

client.CreateShardKey(context.Background(), "{collection_name}", &qdrant.CreateShardKey{
 ShardKey: qdrant.NewShardKey("default"),
})
`
```


Since the collection will allow both dedicated and shared tenants, we need still need to configure payload-based tenancy for this collection the same way as described in the Partition by payload section above. Namely, we need to create a payload index for the `group_id` field with `is_tenant=true`.

`PUT /collections/{collection_name}/index
{
 "field_name": "group_id",
 "field_schema": {
 "type": "keyword",
 "is_tenant": true
 }
}
`
```


`client.create_payload_index(
 collection_name="{collection_name}",
 field_name="group_id",
 field_schema=models.KeywordIndexParams(
 type=models.KeywordIndexType.KEYWORD,
 is_tenant=True,
 ),
)
`
```


`client.createPayloadIndex("{collection_name}", {
 field_name: "group_id",
 field_schema: {
 type: "keyword",
 is_tenant: true,
 },
});
`
```


`use qdrant_client::qdrant::{
 CreateFieldIndexCollectionBuilder,
 KeywordIndexParamsBuilder,
 FieldType
};
use qdrant_client::Qdrant;

let client = Qdrant::from_url("http://localhost:6334").build()?;

client.create_field_index(
 CreateFieldIndexCollectionBuilder::new(
 "{collection_name}",
 "group_id",
 FieldType::Keyword,
 ).field_index_params(
 KeywordIndexParamsBuilder::default()
 .is_tenant(true)
 )
 ).await?;
`
```


`import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Collections.KeywordIndexParams;
import io.qdrant.client.grpc.Collections.PayloadIndexParams;
import io.qdrant.client.grpc.Collections.PayloadSchemaType;

QdrantClient client =
 new QdrantClient(QdrantGrpcClient.newBuilder("localhost", 6334, false).build());

client
 .createPayloadIndexAsync(
 "{collection_name}",
 "group_id",
 PayloadSchemaType.Keyword,
 PayloadIndexParams.newBuilder()
 .setKeywordIndexParams(
 KeywordIndexParams.newBuilder()
 .setIsTenant(true)
 .build())
 .build(),
 null,
 null,
 null)
 .get();
`
```


`using Qdrant.Client;
using Qdrant.Client.Grpc;

var client = new QdrantClient("localhost", 6334);

await client.CreatePayloadIndexAsync(
 collectionName: "{collection_name}",
 fieldName: "group_id",
 schemaType: PayloadSchemaType.Keyword,
 indexParams: new PayloadIndexParams
 {
 KeywordIndexParams = new KeywordIndexParams
 {
 IsTenant = true
 }
 }
);
`
```


`import (
 "context"

 "github.com/qdrant/go-client/qdrant"
)

client, err := qdrant.NewClient(&qdrant.Config{
 Host: "localhost",
 Port: 6334,
})

client.CreateFieldIndex(context.Background(), &qdrant.CreateFieldIndexCollection{
 CollectionName: "{collection_name}",
 FieldName: "group_id",
 FieldType: qdrant.FieldType_FieldTypeKeyword.Enum(),
 FieldIndexParams: qdrant.NewPayloadIndexParams(
 &qdrant.KeywordIndexParams{
 IsTenant: qdrant.PtrOf(true),
 }),
})
`
```


### Query tiered multitenant collection


Now we can start uploading data into the collection. One important difference from the simple payload-based multitenancy is that now we need to specify the Shard Key Selector in each request to route requests to the correct Shard.

Shard Key Selector will specify two keys:
- arget` shard - name of the tenant’s dedicated Shard (which may or may not exist).
- `fallback` shard - name of the shared Fallback Shard (in our case, `default`).

`PUT /collections/{collection_name}/points
{
 "points": [
 {
 "id": 1,
 "payload": {"group_id": "user_1"},
 "vector": [0.9, 0.1, 0.1]
 }
 ],
 "shard_key": {
 "fallback": "default",
 "target": "user_1"
 }
}
`
```


`client.upsert(
 collection_name="{collection_name}",
 points=[
 models.PointStruct(
 id=1,
 payload={"group_id": "user_1"},
 vector=[0.9, 0.1, 0.1],
 ),
 ],
 shard_key_selector=models.ShardKeyWithFallback(
 target="user_1",
 fallback="default"
 )
)
`
```


`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.upsert("{collection_name}", {
 points: [
 {
 id: 1,
 payload: { group_id: "user_1" },
 vector: [0.9, 0.1, 0.1],
 }
 ],
 shard_key: {
 target: "user_1",
 fallback: "default"
 }
});
`
```


`use qdrant_client::Qdrant;
use qdrant_client::qdrant::{PointStruct, ShardKeySelectorBuilder, UpsertPointsBuilder};

let client = Qdrant::from_url("http://localhost:6334").build()?;

let shard_key_selector = ShardKeySelectorBuilder::with_shard_key("user_1")
 .fallback("default")
 .build();

client
 .upsert_points(
 UpsertPointsBuilder::new(
 "{collection_name}",
 vec![
 PointStruct::new(
 1,
 vec![0.9, 0.1, 0.1],
 [("group_id", "user_1".into())]
 ),
 ],
 )
 .shard_key_selector(shard_key_selector),
 )
 .await?;
`
```


`import static io.qdrant.client.PointIdFactory.id;
import static io.qdrant.client.ShardKeyFactory.shardKey;
import static io.qdrant.client.ValueFactory.value;
import static io.qdrant.client.VectorsFactory.vectors;

import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Points.PointStruct;
import io.qdrant.client.grpc.Points.ShardKeySelector;
import io.qdrant.client.grpc.Points.UpsertPoints;
import java.util.List;
import java.util.Map;

QdrantClient client =
 new QdrantClient(QdrantGrpcClient.newBuilder("localhost", 6334, false).build());

client
 .upsertAsync(
 UpsertPoints.newBuilder()
 .setCollectionName("{collection_name}")
 .addAllPoints(
 List.of(
 PointStruct.newBuilder()
 .setId(id(1))
 .setVectors(vectors(0.9f, 0.1f, 0.1f))
 .putAllPayload(Map.of("group_id", value("user_1")))
 .build()))
 .setShardKeySelector(
 ShardKeySelector.newBuilder()
 .addShardKeys(shardKey("user_1"))
 .setFallback(shardKey("default"))
 .build())
 .build())
 .get();
`
```


`using Qdrant.Client;
using Qdrant.Client.Grpc;

var client = new QdrantClient("localhost", 6334);

await client.UpsertAsync(
 collectionName: "{collection_name}",
 points: new List<PointStruct>
 {
 new()
 {
 Id = 1,
 Vectors = new[] { 0.9f, 0.1f, 0.1f },
 Payload = { ["group_id"] = "user_1" }
 }
 },
 shardKeySelector: new ShardKeySelector {
 ShardKeys = { new List<ShardKey> { "user_1" } },
 Fallback = new ShardKey { Keyword = "default" }
 }
);
`
```


`import (
 "context"

 "github.com/qdrant/go-client/qdrant"
)

client, err := qdrant.NewClient(&qdrant.Config{
 Host: "localhost",
 Port: 6334,
})

client.Upsert(context.Background(), &qdrant.UpsertPoints{
 CollectionName: "{collection_name}",
 Points: []*qdrant.PointStruct{
 {
 Id: qdrant.NewIDNum(1),
 Vectors: qdrant.NewVectors(0.9, 0.1, 0.1),
 Payload: qdrant.NewValueMap(map[string]any{"group_id": "user_1"}),
 },
 },
 ShardKeySelector: &qdrant.ShardKeySelector{
 ShardKeys: []*qdrant.ShardKey{
 qdrant.NewShardKey("user_1"),
 },
 Fallback: qdrant.NewShardKey("default"),
 },
})
`
```


The routing logic will work as follows:
- If the arget` Shard exists and active, the request will be routed to it.
- If the arget` Shard does not exist, the request will be routed to the `fallback` Shard.

Similarly, when querying points, we need to specify the Shard Key Selector and filter by `group_id`.
Note, that filter match value should always match the arget` Shard Key.

### Promote tenant to dedicated Shard


When a tenant grows large enough, you can promote it to its own dedicated Shard.
In order to do that, you first need to create a new Shard for the tenant:

`PUT /collections/{collection_name}/shards
{
 "shard_key": "user_1",
 "initial_state": "Partial"
}
`
```


`from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.create_shard_key(
 "{collection_name}",
 shard_key="user_1",
 initial_state=models.ReplicaState.PARTIAL
)
`
```


`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.createShardKey("{collection_name}", {
 shard_key: "default",
 initial_state: "Partial"
});
`
```


`use qdrant_client::qdrant::{
 CreateShardKeyBuilder, CreateShardKeyRequestBuilder
};
use qdrant_client::qdrant::ReplicaState;
use qdrant_client::Qdrant;

let client = Qdrant::from_url("http://localhost:6334").build()?;

client
 .create_shard_key(
 CreateShardKeyRequestBuilder::new("{collection_name}")
 .request(
 CreateShardKeyBuilder::default()
 .shard_key("user_1".to_string())
 .initial_state(ReplicaState::Partial)
 ),
 )
 .await?;
`
```


`import static io.qdrant.client.ShardKeyFactory.shardKey;

import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Collections.CreateShardKey;
import io.qdrant.client.grpc.Collections.CreateShardKeyRequest;
import io.qdrant.client.grpc.Collections.ReplicaState;
import io.qdrant.client.grpc.Common.Filter;

QdrantClient client =
 new QdrantClient(QdrantGrpcClient.newBuilder("localhost", 6334, false).build());

client.createShardKeyAsync(CreateShardKeyRequest.newBuilder()
 .setCollectionName("{collection_name}")
 .setRequest(CreateShardKey.newBuilder()
 .setShardKey(shardKey("default"))
 .setInitialState(ReplicaState.Partial)
 .build())
 .build()).get();
`
```


`using Qdrant.Client;
using Qdrant.Client.Grpc;

var client = new QdrantClient("localhost", 6334);

await client.CreateShardKeyAsync(
 "{collection_name}",
 new CreateShardKey {
 ShardKey = new ShardKey { Keyword = "default" },
 InitialState = ReplicaState.Partial
 }
);
`
```


`import (
 "context"

 "github.com/qdrant/go-client/qdrant"
)

client, err := qdrant.NewClient(&qdrant.Config{
 Host: "localhost",
 Port: 6334,
})

client.CreateShardKey(
 context.Background(),
 "{collection_name}",
 &qdrant.CreateShardKey{
 ShardKey: qdrant.NewShardKey("default"),
 InitialState: qdrant.PtrOf(qdrant.ReplicaState_Partial),
 },
)
`
```


Note, that we create a Shard in `Partial` state, since it would still need to transfer data into it.

To initiate data transfer, there is another API method called eplicate_points`:

`POST /collections/{collection_name}/cluster
{
 "replicate_points": {
 "filter": {
 "must": {
 "key": "group_id",
 "match": {
 "value": "user_1"
 }
 }
 },
 "from_shard_key": "default",
 "to_shard_key": "user_1"
 }
}
`
```


`from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.cluster_collection_update(
 collection_name="{collection_name}",
 cluster_operation=models.ReplicatePointsOperation(
 replicate_points=models.ReplicatePoints(
 from_shard_key="default",
 to_shard_key="user_1",
 filter=models.Filter(
 must=[
 models.FieldCondition(
 key="group_id",
 match=models.MatchValue(
 value="user_1",
 )
 )
 ]
 )
 )
 )
)
`
```


`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.updateCollectionCluster("{collection_name}", {
 replicate_points: {
 filter: {
 must: {
 key: "group_id",
 match: {
 value: "user_1"
 }
 }
 },
 from_shard_key: "default",
 to_shard_key: "user_1"
 }
});
`
```


`use qdrant_client::qdrant::{
 update_collection_cluster_setup_request::Operation, Condition, Filter,
 ReplicatePointsBuilder, ShardKey, UpdateCollectionClusterSetupRequest,
};
use qdrant_client::Qdrant;

let client = Qdrant::from_url("http://localhost:6334").build()?;

client
 .update_collection_cluster_setup(UpdateCollectionClusterSetupRequest {
 collection_name: "{collection_name}".to_string(),
 operation: Some(Operation::ReplicatePoints(
 ReplicatePointsBuilder::new(
 ShardKey::from("default"),
 ShardKey::from("user_1"),
 )
 .filter(Filter::must([Condition::matches(
 "group_id",
 "user_1".to_string(),
 )]))
 .build(),
 )),
 timeout: None,
 })
 .await?;
`
```


`import static io.qdrant.client.ConditionFactory.matchKeyword;
import static io.qdrant.client.QueryFactory.nearest;
import static io.qdrant.client.ShardKeyFactory.shardKey;

import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Collections.ReplicatePoints;
import io.qdrant.client.grpc.Collections.UpdateCollectionClusterSetupRequest;
import io.qdrant.client.grpc.Common.Filter;

QdrantClient client =
 new QdrantClient(QdrantGrpcClient.newBuilder("localhost", 6334, false).build());

client
 .updateCollectionClusterSetupAsync(
 UpdateCollectionClusterSetupRequest.newBuilder()
 .setCollectionName("{collection_name}")
 .setReplicatePoints(
 ReplicatePoints.newBuilder()
 .setFromShardKey(shardKey("default"))
 .setToShardKey(shardKey("user_1"))
 .setFilter(
 Filter.newBuilder().addMust(matchKeyword("group_id", "user_1")).build())
 .build())
 .build())
 .get();
`
```


`using Qdrant.Client;
using Qdrant.Client.Grpc;
using static Qdrant.Client.Grpc.Conditions;

var client = new QdrantClient("localhost", 6334);

await client.UpdateCollectionClusterSetupAsync(new()
{
 CollectionName = "{collection_name}",
 ReplicatePoints = new()
 {
 FromShardKey = "default",
 ToShardKey = "user_1",
 Filter = MatchKeyword("group_id", "user_1")
 }
});
`
```


`import (
 "context"

 "github.com/qdrant/go-client/qdrant"
)

client, err := qdrant.NewClient(&qdrant.Config{
 Host: "localhost",
 Port: 6334,
})

client.UpdateClusterCollectionSetup(context.Background(), qdrant.NewUpdateCollectionClusterReplicatePoints(
 "{collection_name}", &qdrant.ReplicatePoints{
 FromShardKey: qdrant.NewShardKey("default"),
 ToShardKey: qdrant.NewShardKey("user_1"),
 Filter: &qdrant.Filter{
 Must: []*qdrant.Condition{
 qdrant.NewMatch("group_id", "user_1"),
 },
 },
 },
))
`
```


Once transfer is completed, target Shard will become `Active`, and all requests for the tenant will be routed to it automatically.
At this point it is safe to delete the tenant’s data from the shared Fallback Shard to free up space.

### Limitations

- Currently, `fallback` Shard may only contain a single shard ID on its own. That means all small tenants must fit a single peer of the cluster. This restriction will be improved in future releases.
- Similar to collections, dedicated Shards introduce some resource overhead. It is not recommended to create more than a thousand dedicated Shards per cluster. Recommended threshold of promoting a tenant is the same as the indexing threshold for a single collection, which is around 20K points.

##### Was this page useful?


Yes


No

Thank you for your feedback! 🙏

We are sorry to hear that. 😔 You can edit this page on GitHub, or create a GitHub issue.

Create an issue
