<!-- source: Qdrant Memory -->
<!-- cleaned: nav-bar removed -->

# Monitor Collection Memory Usage


Available as of v1.18.0

Qdrant lets you inspect a collection’s disk space, RAM, and OS page cache usage, summed up across the whole cluster and broken down by component. Use this to plan capacity, diagnose memory pressure, or understand which parts of a collection are resident in memory.

This information is available in the Qdrant Web UI and through the API.
## Web UI


Open the collection detail page and select the Memory tab. It shows the memory breakdown for the collection, updated on demand.The Memory tab shows the breakdown of disk, RAM, and cached usage for each component of the collection.
## Understanding the Fields


The breakdown covers these components:ComponentDescriptionTotalAggregate across all components.VectorsPer dense and multi-dense vector: storage, index, and optionally quantization.Sparse VectorsPer sparse vector: storage and index.PayloadPayload storage.Payload IndexPer payload field index.ID TrackerMaps external point IDs to internal ones.

Each component reports four values:FieldDescriptionDiskTotal file sizes on disk.RAMNon-evictable heap RAM: in-memory data structures not backed by memory-mapped files.CachedEvictable RAM: file pages currently resident in the OS page cache.Expected CacheThe amount of data that should ideally be cached for best performance. Compare this against Cached to see how much of the working set is warm.
## API


You can retrieve the same data though Qdrant’s API:

`curl http://localhost:6333/collections/{collection_name}/memory
`
## Accuracy


The reported values are estimates. RAM usage is typically underestimated by 10–15% because memory allocated by third-party libraries and the allocator itself isn’t accounted for.

On non-Unix systems, Cached is always reported as `.
##### Was this page useful?


Yes


No

Thank you for your feedback! 🙏

We are sorry to hear that. 😔 You can edit this page on GitHub, or create a GitHub issue.


Create an issue
