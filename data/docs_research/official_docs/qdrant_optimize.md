<!-- source: Qdrant Optimize -->
<!-- cleaned: nav-bar removed -->

# Optimizing Qdrant Performance: Three Scenarios


Different use cases require different balances between memory usage, search speed, and precision. Qdrant is designed to be flexible and customizable so you can tune it to your specific needs.

This guide will walk you three main optimization strategies:
- High Speed Search & Low Memory Usage
- High Precision & Low Memory Usage
- High Precision & High Speed Search


## 1. High-Speed Search with Low Memory Usage


To achieve high search speed with minimal memory usage, you can store vectors on disk while minimizing the number of disk reads. Vector quantization is a technique that compresses vectors, allowing more of them to be stored in memory, thus reducing the need to read from disk.

To configure in-memory quantization, with on-disk original vectors, you need to create a collection with the following parameters:
- `on_disk`: Stores original vectors on disk.
- `quantization_config`: Compresses quantized vectors to `int8` using the `scalar` method.
- lways_ram`: Keeps quantized vectors in RAM.

`PUT /collections/{collection_name}
{
 "vectors": {
 "size": 768,
 "distance": "Cosine",
 "on_disk": true
 },
 "quantization_config": {
 "scalar": {
 "type": "int8",
 "always_ram": true
 }
 }
}
`

`from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
 collection_name="{collection_name}",
 vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE, on_disk=True),
 quantization_config=models.ScalarQuantization(
 scalar=models.ScalarQuantizationConfig(
 type=models.ScalarType.INT8,
 always_ram=True,
 ),
 ),
)
`

`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.createCollection("{collection_name}", {
 vectors: {
 size: 768,
 distance: "Cosine",
 on_disk: true,
 },
 quantization_config: {
 scalar: {
 type: "int8",
 always_ram: true,
 },
 },
});
`

`use qdrant_client::qdrant::{
 CreateCollectionBuilder, Distance, QuantizationType, ScalarQuantizationBuilder,
 VectorParamsBuilder,
};
use qdrant_client::Qdrant;

let client = Qdrant::from_url("http://localhost:6334").build()?;

client
 .create_collection(
 CreateCollectionBuilder::new("{collection_name}")
 .vectors_config(VectorParamsBuilder::new(768, Distance::Cosine))
 .quantization_config(
 ScalarQuantizationBuilder::default()
 .r#type(QuantizationType::Int8.into())
 .always_ram(true),
 ),
 )
 .await?;
`

`import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Collections.CreateCollection;
import io.qdrant.client.grpc.Collections.Distance;
import io.qdrant.client.grpc.Collections.OptimizersConfigDiff;
import io.qdrant.client.grpc.Collections.QuantizationConfig;
import io.qdrant.client.grpc.Collections.QuantizationType;
import io.qdrant.client.grpc.Collections.ScalarQuantization;
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
 .setOnDisk(true)
 .build())
 .build())
 .setQuantizationConfig(
 QuantizationConfig.newBuilder()
 .setScalar(
 ScalarQuantization.newBuilder()
 .setType(QuantizationType.Int8)
 .setAlwaysRam(true)
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
 vectorsConfig: new VectorParams { Size = 768, Distance = Distance.Cosine, OnDisk = true },
 quantizationConfig: new QuantizationConfig
 {
 Scalar = new ScalarQuantization { Type = QuantizationType.Int8, AlwaysRam = true }
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
 VectorsConfig: qdrant.NewVectorsConfig(&qdrant.VectorParams{
 Size: 768,
 Distance: qdrant.Distance_Cosine,
 OnDisk: qdrant.PtrOf(true),
 }),
 QuantizationConfig: qdrant.NewQuantizationScalar(&qdrant.ScalarQuantization{
 Type: qdrant.QuantizationType_Int8,
 AlwaysRam: qdrant.PtrOf(true),
 }),
})
`
### Disable Rescoring for Faster Search (optional)


This is completely optional. Disabling rescoring with search `params` can further reduce the number of disk reads. Note that this might slightly decrease precision.

`POST /collections/{collection_name}/points/query
{
 "query": [0.2, 0.1, 0.9, 0.7],
 "params": {
 "quantization": {
 "rescore": false
 }
 },
 "limit": 10
}
`

`from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.query_points(
 collection_name="{collection_name}",
 query=[0.2, 0.1, 0.9, 0.7],
 search_params=models.SearchParams(
 quantization=models.QuantizationSearchParams(rescore=False)
 ),
)
`

`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.query("{collection_name}", {
 query: [0.2, 0.1, 0.9, 0.7],
 params: {
 quantization: {
 rescore: false,
 },
 },
});
`

`use qdrant_client::qdrant::{
 QuantizationSearchParamsBuilder, QueryPointsBuilder, SearchParamsBuilder,
};
use qdrant_client::Qdrant;

let client = Qdrant::from_url("http://localhost:6334").build()?;

client
 .query(
 QueryPointsBuilder::new("{collection_name}")
 .query(vec![0.2, 0.1, 0.9, 0.7])
 .limit(3)
 .params(
 SearchParamsBuilder::default()
 .quantization(QuantizationSearchParamsBuilder::default().rescore(false)),
 ),
 )
 .await?;
`

`import static io.qdrant.client.QueryFactory.nearest;

import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Points.QuantizationSearchParams;
import io.qdrant.client.grpc.Points.QueryPoints;
import io.qdrant.client.grpc.Points.SearchParams;

QdrantClient client =
 new QdrantClient(QdrantGrpcClient.newBuilder("localhost", 6334, false).build());

client.queryAsync(
 QueryPoints.newBuilder()
 .setCollectionName("{collection_name}")
 .setQuery(nearest(0.2f, 0.1f, 0.9f, 0.7f))
 .setParams(
 SearchParams.newBuilder()
 .setQuantization(
 QuantizationSearchParams.newBuilder().setRescore(false).build())
 .build())
 .setLimit(3)
 .build())
 .get();
`

`using Qdrant.Client;
using Qdrant.Client.Grpc;

var client = new QdrantClient("localhost", 6334);

await client.QueryAsync(
 collectionName: "{collection_name}",
 query: new float[] { 0.2f, 0.1f, 0.9f, 0.7f },
 searchParams: new SearchParams
 {
 Quantization = new QuantizationSearchParams { Rescore = false }
 },
 limit: 3
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

client.Query(context.Background(), &qdrant.QueryPoints{
 CollectionName: "{collection_name}",
 Query: qdrant.NewQuery(0.2, 0.1, 0.9, 0.7),
 Params: &qdrant.SearchParams{
 Quantization: &qdrant.QuantizationSearchParams{
 Rescore: qdrant.PtrOf(true),
 },
 },
})
`
## 2. High Precision with Low Memory Usage


If you require high precision but have limited RAM, you can store both vectors and the HNSW index on disk. This setup reduces memory usage while maintaining search precision.

To store the vectors `on_disk`, you need to configure both the vectors and the HNSW index:

`PUT /collections/{collection_name}
{
 "vectors": {
 "size": 768,
 "distance": "Cosine",
 "on_disk": true
 },
 "hnsw_config": {
 "on_disk": true
 }
}
`

`from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
 collection_name="{collection_name}",
 vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE, on_disk=True),
 hnsw_config=models.HnswConfigDiff(on_disk=True),
)
`

`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.createCollection("{collection_name}", {
 vectors: {
 size: 768,
 distance: "Cosine",
 on_disk: true,
 },
 hnsw_config: {
 on_disk: true,
 },
});
`

`use qdrant_client::qdrant::{
 CreateCollectionBuilder, Distance, HnswConfigDiffBuilder,
 VectorParamsBuilder,
};
use qdrant_client::Qdrant;

let client = Qdrant::from_url("http://localhost:6334").build()?;

client
 .create_collection(
 CreateCollectionBuilder::new("{collection_name}")
 .vectors_config(VectorParamsBuilder::new(768, Distance::Cosine).on_disk(true))
 .hnsw_config(HnswConfigDiffBuilder::default().on_disk(true)),
 )
 .await?;
`

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
 .setOnDisk(true)
 .build())
 .build())
 .setHnswConfig(HnswConfigDiff.newBuilder().setOnDisk(true).build())
 .build())
 .get();
`

`using Qdrant.Client;
using Qdrant.Client.Grpc;

var client = new QdrantClient("localhost", 6334);

await client.CreateCollectionAsync(
 collectionName: "{collection_name}",
 vectorsConfig: new VectorParams { Size = 768, Distance = Distance.Cosine, OnDisk = true },
 hnswConfig: new HnswConfigDiff { OnDisk = true }
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
 VectorsConfig: qdrant.NewVectorsConfig(&qdrant.VectorParams{
 Size: 768,
 Distance: qdrant.Distance_Cosine,
 OnDisk: qdrant.PtrOf(true),
 }),
 HnswConfig: &qdrant.HnswConfigDiff{
 OnDisk: qdrant.PtrOf(true),
 },
})
`
### Improving Precision


Increase the `ef` and `m` parameters of the HNSW index to improve precision, even with limited RAM:

`...
"hnsw_config": {
 "m": 64,
 "ef_construct": 512,
 "on_disk": true
}
...
`

Note: The speed of this setup depends on the disk’s IOPS (Input/Output Operations Per Second).You can use fio to measure disk IOPS.
### Inline Storage in HNSW Index


Available as of v1.16.0

When storing vectors and the HNSW index on disk, you can improve search performance by enabling the `inline_storage` option in the `hnsw_config`.
With inline storage, Qdrant stores copies of vectors directly within the HNSW index file.
It makes searches faster by reducing the number of IO operations, at the cost of 3-4x increased storage usage.
It requires quantization to be enabled.

`PUT /collections/{collection_name}
{
 "vectors": {
 "size": 768,
 "distance": "Cosine",
 "on_disk": true
 },
 "quantization_config": {
 "binary": {
 "always_ram": false
 }
 },
 "hnsw_config": {
 "on_disk": true,
 "inline_storage": true
 }
}
`

`from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
 collection_name="{collection_name}",
 vectors_config=models.VectorParams(
 size=768, distance=models.Distance.COSINE, on_disk=True
 ),
 quantization_config=models.BinaryQuantization(
 binary=models.BinaryQuantizationConfig(always_ram=False),
 ),
 hnsw_config=models.HnswConfigDiff(on_disk=True, inline_storage=True),
)
`

`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.createCollection("{collection_name}", {
 vectors: {
 size: 768,
 distance: "Cosine",
 on_disk: true,
 },
 quantization_config: {
 binary: {
 always_ram: false,
 },
 },
 hnsw_config: {
 on_disk: true,
 inline_storage: true,
 },
});
`

`use qdrant_client::Qdrant;
use qdrant_client::qdrant::{
 BinaryQuantizationBuilder, CreateCollectionBuilder, Distance, HnswConfigDiffBuilder,
 VectorParamsBuilder,
};

let client = Qdrant::from_url("http://localhost:6334").build()?;

client
 .create_collection(
 CreateCollectionBuilder::new("{collection_name}")
 .vectors_config(VectorParamsBuilder::new(768, Distance::Cosine).on_disk(true))
 .quantization_config(BinaryQuantizationBuilder::new(false))
 .hnsw_config(
 HnswConfigDiffBuilder::default()
 .on_disk(true)
 .inline_storage(true),
 ),
 )
 .await?;
`

`import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Collections.BinaryQuantization;
import io.qdrant.client.grpc.Collections.CreateCollection;
import io.qdrant.client.grpc.Collections.Distance;
import io.qdrant.client.grpc.Collections.HnswConfigDiff;
import io.qdrant.client.grpc.Collections.QuantizationConfig;
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
 .setOnDisk(true)
 .build())
 .build())
 .setQuantizationConfig(
 QuantizationConfig.newBuilder()
 .setBinary(BinaryQuantization.newBuilder().setAlwaysRam(false).build())
 .build())
 .setHnswConfig(HnswConfigDiff.newBuilder().setOnDisk(true).setInlineStorage(true).build())
 .build())
 .get();
`

`using Qdrant.Client;
using Qdrant.Client.Grpc;

var client = new QdrantClient("localhost", 6334);

await client.CreateCollectionAsync(
 collectionName: "{collection_name}",
 vectorsConfig: new VectorParams { Size = 768, Distance = Distance.Cosine, OnDisk = true },
 quantizationConfig: new QuantizationConfig
 {
 Binary = new BinaryQuantization { AlwaysRam = false }
 },
 hnswConfig: new HnswConfigDiff { OnDisk = true, InlineStorage = true }
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
 VectorsConfig: qdrant.NewVectorsConfig(&qdrant.VectorParams{
 Size: 768,
 Distance: qdrant.Distance_Cosine,
 OnDisk: qdrant.PtrOf(true),
 }),
 QuantizationConfig: qdrant.NewQuantizationBinary(
 &qdrant.BinaryQuantization{
 AlwaysRam: qdrant.PtrOf(false),
 },
 ),
 HnswConfig: &qdrant.HnswConfigDiff{
 OnDisk: qdrant.PtrOf(true),
 InlineStorage: qdrant.PtrOf(true),
 },
})
`
## 3. High Precision with High-Speed Search


For scenarios requiring both high speed and high precision, keep as much data in RAM as possible. Apply quantization with re-scoring for tunable accuracy.

Here is how you can configure scalar quantization for a collection:

`PUT /collections/{collection_name}
{
 "vectors": {
 "size": 768,
 "distance": "Cosine"
 },
 "quantization_config": {
 "scalar": {
 "type": "int8",
 "always_ram": true
 }
 }
}
`

`from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
 collection_name="{collection_name}",
 vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE),
 quantization_config=models.ScalarQuantization(
 scalar=models.ScalarQuantizationConfig(
 type=models.ScalarType.INT8,
 always_ram=True,
 ),
 ),
)
`

`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.createCollection("{collection_name}", {
 vectors: {
 size: 768,
 distance: "Cosine",
 },
 quantization_config: {
 scalar: {
 type: "int8",
 always_ram: true,
 },
 },
});
`

`use qdrant_client::qdrant::{
 CreateCollectionBuilder, Distance, QuantizationType, ScalarQuantizationBuilder,
 VectorParamsBuilder,
};
use qdrant_client::Qdrant;

let client = Qdrant::from_url("http://localhost:6334").build()?;

client
 .create_collection(
 CreateCollectionBuilder::new("{collection_name}")
 .vectors_config(VectorParamsBuilder::new(768, Distance::Cosine))
 .quantization_config(
 ScalarQuantizationBuilder::default()
 .r#type(QuantizationType::Int8.into())
 .always_ram(true),
 ),
 )
 .await?;
`

`import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Collections.CreateCollection;
import io.qdrant.client.grpc.Collections.Distance;
import io.qdrant.client.grpc.Collections.OptimizersConfigDiff;
import io.qdrant.client.grpc.Collections.QuantizationConfig;
import io.qdrant.client.grpc.Collections.QuantizationType;
import io.qdrant.client.grpc.Collections.ScalarQuantization;
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
 .setQuantizationConfig(
 QuantizationConfig.newBuilder()
 .setScalar(
 ScalarQuantization.newBuilder()
 .setType(QuantizationType.Int8)
 .setAlwaysRam(true)
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
 vectorsConfig: new VectorParams { Size = 768, Distance = Distance.Cosine},
 quantizationConfig: new QuantizationConfig
 {
 Scalar = new ScalarQuantization { Type = QuantizationType.Int8, AlwaysRam = true }
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
 VectorsConfig: qdrant.NewVectorsConfig(&qdrant.VectorParams{
 Size: 768,
 Distance: qdrant.Distance_Cosine,
 }),
 QuantizationConfig: qdrant.NewQuantizationScalar(&qdrant.ScalarQuantization{
 Type: qdrant.QuantizationType_Int8,
 AlwaysRam: qdrant.PtrOf(true),
 }),
})
`
### Fine-Tuning Search Parameters


You can adjust search parameters like `hnsw_ef` and `exact` to balance between speed and precision:

Key Parameters:
- `hnsw_ef`: Number of neighbors to visit during search (higher value = better accuracy, slower speed).
- `exact`: Set to rue` for exact search, which is slower but more accurate. You can use it to compare results of the search with different `hnsw_ef` values versus the ground truth.

`POST /collections/{collection_name}/points/query
{
 "query": [0.2, 0.1, 0.9, 0.7],
 "params": {
 "hnsw_ef": 128,
 "exact": false
 },
 "limit": 3
}
`

`from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.query_points(
 collection_name="{collection_name}",
 query=[0.2, 0.1, 0.9, 0.7],
 search_params=models.SearchParams(hnsw_ef=128, exact=False),
 limit=3,
)
`

`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.query("{collection_name}", {
 query: [0.2, 0.1, 0.9, 0.7],
 params: {
 hnsw_ef: 128,
 exact: false,
 },
 limit: 3,
});
`

`use qdrant_client::qdrant::{QueryPointsBuilder, SearchParamsBuilder};
use qdrant_client::Qdrant;

let client = Qdrant::from_url("http://localhost:6334").build()?;

client
 .query(
 QueryPointsBuilder::new("{collection_name}")
 .query(vec![0.2, 0.1, 0.9, 0.7])
 .limit(3)
 .params(SearchParamsBuilder::default().hnsw_ef(128).exact(false)),
 )
 .await?;
`

`import static io.qdrant.client.QueryFactory.nearest;

import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Points.QueryPoints;
import io.qdrant.client.grpc.Points.SearchParams;

QdrantClient client =
 new QdrantClient(QdrantGrpcClient.newBuilder("localhost", 6334, false).build());

client.queryAsync(
 QueryPoints.newBuilder()
 .setCollectionName("{collection_name}")
 .setQuery(nearest(0.2f, 0.1f, 0.9f, 0.7f))
 .setParams(SearchParams.newBuilder().setHnswEf(128).setExact(false).build())
 .setLimit(3)
 .build())
 .get();
`

`using Qdrant.Client;
using Qdrant.Client.Grpc;

var client = new QdrantClient("localhost", 6334);

await client.QueryAsync(
 collectionName: "{collection_name}",
 query: new float[] { 0.2f, 0.1f, 0.9f, 0.7f },
 searchParams: new SearchParams { HnswEf = 128, Exact = false },
 limit: 3
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

client.Query(context.Background(), &qdrant.QueryPoints{
 CollectionName: "{collection_name}",
 Query: qdrant.NewQuery(0.2, 0.1, 0.9, 0.7),
 Params: &qdrant.SearchParams{
 HnswEf: qdrant.PtrOf(uint64(128)),
 Exact: qdrant.PtrOf(false),
 },
})
`
## Balancing Latency and Throughput


When optimizing search performance, latency and throughput are two main metrics to consider:
- Latency: Time taken for a single request.
- Throughput: Number of requests handled per second.

The following optimization approaches are not mutually exclusive, but in some cases it might be preferable to optimize for one or another.
### Minimizing Latency


To minimize latency, you can set up Qdrant to use as many cores as possible for a single request.
You can do this by setting the number of segments in the collection to be equal to the number of cores in the system.

In this case, each segment will be processed in parallel, and the final result will be obtained faster.

`PUT /collections/{collection_name}
{
 "vectors": {
 "size": 768,
 "distance": "Cosine"
 },
 "optimizers_config": {
 "default_segment_number": 16
 }
}
`

`from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
 collection_name="{collection_name}",
 vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE),
 optimizers_config=models.OptimizersConfigDiff(default_segment_number=16),
)
`

`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.createCollection("{collection_name}", {
 vectors: {
 size: 768,
 distance: "Cosine",
 },
 optimizers_config: {
 default_segment_number: 16,
 },
});
`

`use qdrant_client::qdrant::{
 CreateCollectionBuilder, Distance, OptimizersConfigDiffBuilder, VectorParamsBuilder,
};
use qdrant_client::Qdrant;

let client = Qdrant::from_url("http://localhost:6334").build()?;

client
 .create_collection(
 CreateCollectionBuilder::new("{collection_name}")
 .vectors_config(VectorParamsBuilder::new(768, Distance::Cosine))
 .optimizers_config(
 OptimizersConfigDiffBuilder::default().default_segment_number(16),
 ),
 )
 .await?;
`

`import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Collections.CreateCollection;
import io.qdrant.client.grpc.Collections.Distance;
import io.qdrant.client.grpc.Collections.OptimizersConfigDiff;
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
 .setOptimizersConfig(
 OptimizersConfigDiff.newBuilder().setDefaultSegmentNumber(16).build())
 .build())
 .get();
`

`using Qdrant.Client;
using Qdrant.Client.Grpc;

var client = new QdrantClient("localhost", 6334);

await client.CreateCollectionAsync(
 collectionName: "{collection_name}",
 vectorsConfig: new VectorParams { Size = 768, Distance = Distance.Cosine },
 optimizersConfig: new OptimizersConfigDiff { DefaultSegmentNumber = 16 }
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
 VectorsConfig: qdrant.NewVectorsConfig(&qdrant.VectorParams{
 Size: 768,
 Distance: qdrant.Distance_Cosine,
 }),
 OptimizersConfig: &qdrant.OptimizersConfigDiff{
 DefaultSegmentNumber: qdrant.PtrOf(uint64(16)),
 },
})
`
### Maximizing Throughput


To maximize throughput, configure Qdrant to use as many cores as possible to process multiple requests in parallel.

To do that, use fewer segments (usually 2) of larger size (default 200Mb per segment) to handle more requests in parallel.

Large segments benefit from the size of the index and overall smaller number of vector comparisons required to find the nearest neighbors. However, they will require more time to build the HNSW index.

`PUT /collections/{collection_name}
{
 "vectors": {
 "size": 768,
 "distance": "Cosine"
 },
 "optimizers_config": {
 "default_segment_number": 2,
 "max_segment_size": 5000000
 }
}
`

`from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
 collection_name="{collection_name}",
 vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE),
 optimizers_config=models.OptimizersConfigDiff(default_segment_number=2, max_segment_size=5000000),
)
`

`import { QdrantClient } from "@qdrant/js-client-rest";

const client = new QdrantClient({ host: "localhost", port: 6333 });

client.createCollection("{collection_name}", {
 vectors: {
 size: 768,
 distance: "Cosine",
 },
 optimizers_config: {
 default_segment_number: 2,
 max_segment_size: 5000000,
 },
});
`

`use qdrant_client::qdrant::{
 CreateCollectionBuilder, Distance, OptimizersConfigDiffBuilder, VectorParamsBuilder,
};
use qdrant_client::Qdrant;

let client = Qdrant::from_url("http://localhost:6334").build()?;

client
 .create_collection(
 CreateCollectionBuilder::new("{collection_name}")
 .vectors_config(VectorParamsBuilder::new(768, Distance::Cosine))
 .optimizers_config(
 OptimizersConfigDiffBuilder::default().default_segment_number(2).max_segment_size(5000000),
 ),
 )
 .await?;
`

`import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import io.qdrant.client.grpc.Collections.CreateCollection;
import io.qdrant.client.grpc.Collections.Distance;
import io.qdrant.client.grpc.Collections.OptimizersConfigDiff;
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
 .setOptimizersConfig(
 OptimizersConfigDiff.newBuilder()
 .setDefaultSegmentNumber(2)
 .setMaxSegmentSize(5000000)
 .build()
 )
 .build())
 .get();
`

`using Qdrant.Client;
using Qdrant.Client.Grpc;

var client = new QdrantClient("localhost", 6334);

await client.CreateCollectionAsync(
 collectionName: "{collection_name}",
 vectorsConfig: new VectorParams { Size = 768, Distance = Distance.Cosine },
 optimizersConfig: new OptimizersConfigDiff { DefaultSegmentNumber = 2, MaxSegmentSize = 5000000 }
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
 VectorsConfig: qdrant.NewVectorsConfig(&qdrant.VectorParams{
 Size: 768,
 Distance: qdrant.Distance_Cosine,
 }),
 OptimizersConfig: &qdrant.OptimizersConfigDiff{
 DefaultSegmentNumber: qdrant.PtrOf(uint64(2)),
 MaxSegmentSize: qdrant.PtrOf(uint64(5000000)),
 },
})
`
## Summary


By adjusting configurations like vector storage, quantization, and search parameters, you can optimize Qdrant for different use cases:
- Low Memory + High Speed: Use vector quantization.
- High Precision + Low Memory: Store vectors and HNSW index on disk.
- High Precision + High Speed: Keep data in RAM, use quantization with re-scoring.
- Latency vs. Throughput: Adjust segment numbers based on the priority.

Choose the strategy that best fits your use case to get the most out of Qdrant’s performance capabilities.
##### Was this page useful?


Yes


No

Thank you for your feedback! 🙏

We are sorry to hear that. 😔 You can edit this page on GitHub, or create a GitHub issue.


Create an issue
