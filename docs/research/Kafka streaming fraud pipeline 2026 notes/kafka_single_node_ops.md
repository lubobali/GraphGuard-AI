# Running Apache Kafka 4.x as a single-node broker on a small, shared box (as of 21 Nov 2026)

Scope: version, image, memory footprint, single-node KRaft config, security, Docker + k3s pitfalls, alternatives, cheap monitoring. Researched 2026-11-21. "Older" marks information from before 2026. "Vendor claim" marks statements from a company about its own product.

## 1. Current stable Kafka 4.x, what changed in 4.0-4.4, and CVEs

### Takeaway
The latest release is **Kafka 4.4.0 (22 Oct 2026)**. The supported lines are 4.4.0, 4.3.2 and 4.2.2. There were many 2026 CVEs, mostly broker OOM/DoS from malformed requests. All but one are fixed in 4.2.2 / 4.3.2 / 4.4.0, so anything older than those versions should be ruled out. KRaft-only (4.0), KIP-848 GA (4.0) and Kafka Queues production-ready (4.2) are the big changes.

### Cited Findings
- Release list from the official downloads page: 4.4.0 (Oct 22 2026), 4.3.2 (Oct 23 2026), 4.3.1 (Jun 25 2026), 4.3.0 (May 22 2026), 4.2.2 (Sep 29 2026), 4.2.1 (May 30 2026), 4.2.0 (Feb 17 2026), 4.1.2 (Mar 17 2026), 4.1.1 (Nov 12 2025), 4.1.0 (Sep 2 2025), 4.0.2 (Mar 16 2026), 4.0.1 (Oct 13 2025), 4.0.0 (Mar 18 2025). It lists **4.4.0, 4.3.2 and 4.2.2 as the supported releases**. All others are archived. — [Kafka downloads](https://kafka.apache.org/community/downloads/)
  - Date conflict: Confluent dates 4.3.0 to 1 June 2026, but the Apache page says 22 May 2026. — [Confluent 4.3 post](https://www.confluent.io/es-mx/blog/apache-kafka-4-3-release/)
- **4.0 (Mar 2025, older)** was "the first major release to operate entirely without Apache ZooKeeper". KIP-848 (the new consumer rebalance protocol) is GA: brokers enable it by default, but **consumers must set `group.protocol=consumer`**. KIP-932 (Queues/share groups) was early access. Clients and Streams need Java 11. Brokers, Connect and tools need Java 17. Old protocol API versions were removed (KIP-896), and clients and brokers must be ≥ 2.1 to talk to 4.0. Logging moved to Log4j2 (KIP-653). — [4.0.0 announcement](https://kafka.apache.org/blog/2025/03/18/apache-kafka-4.0.0-release-announcement/)
- **4.2.0 (17 Feb 2026)**: Kafka Queues (KIP-932) are "now production-ready", with a RENEW ack type and lag metrics. Java 25 support was added. Several deprecations are marked for removal in 5.0: the ConsumerGroupMetadata constructors, MX4j, BrokerNotFoundException, legacy metric names (KIP-1100) and inconsistent CLI options (KIP-1147). — [4.2.0 announcement](https://kafka.apache.org/blog/2026/02/17/apache-kafka-4.2.0-release-announcement/). Confluent's summary adds that Streams server-side rebalancing is GA and Streams gets DLQ support (vendor blog) — [search result summary of Confluent 4.2 post](https://www.confluent.io/blog/apache-kafka-4-2-release/)
- **4.3.0 (May/Jun 2026)**: `group.coordinator.rebalance.protocols` is deprecated (KIP-1237). Consumers on the classic protocol now log a recommendation to switch to the new one (KIP-1274), and classic will be deprecated later. New share-group configs (KIP-1240). KRaft caps on controller Fetch/FetchSnapshot bytes (KIP-1219). `num.partitions`/`default.replication.factor` are applied consistently at topic creation (KIP-1211). New per-partition retention-usage metrics (KIP-1257). — [Confluent 4.3 post](https://www.confluent.io/es-mx/blog/apache-kafka-4-3-release/)
- **4.4.0 (22 Oct 2026)**: 25 KIPs. Brokers must be the same version as, or newer than, the `kafka-storage` tool that formatted their dirs (KIP-1170). This matters if the format step and broker image versions ever differ. Controller unregistration (KIP-1312). Async bootstrap DNS (KIP-909, `bootstrap.resolve.timeout.ms`, default 0, evolving). Share-group DLQs (KIP-1191, needs `share.version`=2). Streams transactional state stores (KIP-892, opt-in). Linux `/proc/self/io` metrics via JMX (KIP-1291). Deprecations: `broker.id` (KIP-1232) and `kafka-broker-api-versions.sh` (replaced by `kafka-cluster.sh api-versions`). — [4.4.0 announcement](https://kafka.apache.org/blog/2026/10/22/apache-kafka-4.4.0-release-announcement/)
- **CVEs, 2026** (from Apache's own list). Most are fixed in **4.2.2 / 4.3.2 / 4.4.0**: — [Kafka CVE list](https://kafka.apache.org/community/cve-list/)
  - Broker OOM/DoS from crafted input: CVE-2026-114349 (compressed record batch decoding), CVE-2026-111115 (tagged-field amplification), CVE-2026-111108 (array allocation amplification), CVE-2026-111073 (PushTelemetry decompression, fixed 4.3.1/4.2.2/4.4.0). Client/Streams deserializer DoS: CVE-2026-111551.
  - **CVE-2026-112375**: an unauthorized principal can read broker files and env vars via IncrementalAlterConfigs (3.2.0-4.3.1).
  - **CVE-2026-83525**: an authenticated client can crash the KRaft controller through the FetchSnapshot handler.
  - OAUTHBEARER issues: CVE-2026-110985, CVE-2026-33557, and CVE-2026-110952 (issuer/audience not enforced by default, fixed **only in 4.4.0**).
  - Connect REST: CVE-2026-116593, CVE-2026-115644.
  - Client bugs: CVE-2026-35554 (producer buffer-pool race misroutes messages to other topics, fixed 4.0.2/4.1.2/4.2.0) and CVE-2026-33558 (sensitive data logged at DEBUG).
  - **CVE-2026-41115** (4.0.0-4.3.0): CONSUMER_GROUP_DESCRIBE checks DESCRIBE instead of the documented READ. **The list shows no fixed release.** The advice is to review group ACLs.
- CVEs, 2025 (older): CVE-2025-27817/27818/27819 (OAUTHBEARER SSRF/file read, LdapLoginModule/JndiLoginModule RCE), fixed in 3.9.1/4.0.0. 2024 (older): CVE-2024-56128, SCRAM nonce not validated, so replay was possible without TLS (fixed 3.9.0). — [Kafka CVE list](https://kafka.apache.org/community/cve-list/)
- **Java4Shell, CVE-2026-114938** (disclosed 17 Nov 2026) is a memory-corruption flaw in the OpenJDK HotSpot Base64 decoder, affecting Java 17/21/25/27. Severity is disputed: CVSS 9.2 from the discoverer vs 8.1 from Oracle. No in-the-wild exploitation was reported as of 17 Nov. It is a JDK flaw, not a Kafka CVE, but the Kafka 4.4.0 blog's navigation links to a post about it. Most coverage is secondary news sites. — [Strobes](https://strobes.co/blog/java4shell-cve-2026-114938-openjdk-base64-rce/), [Dark Reading](https://darkreading.com/vulnerabilities-threats/java4shell-flaw-threatens-global-java-application-ecosystem), [4.4.0 announcement page nav](https://kafka.apache.org/blog/2026/10/22/apache-kafka-4.4.0-release-announcement/)

### Inferences
- Pick **4.4.0**, or 4.3.2 if waiting for a .1 patch is preferred. 4.4.0 is the only line with the OAUTHBEARER default fix, but that is irrelevant if OAuth is not used. Do not deploy 4.2.0-4.2.1 or 4.3.0-4.3.1: several 2026 DoS CVEs are reachable by any client that can connect.
- For a Python consumer (likely confluent-kafka/librdkafka), KIP-848 only applies if the client library supports `group.protocol=consumer`. Check the client version separately.
- CVE-2026-112375 and CVE-2026-41115 both argue for **per-client principals with minimal ACLs**: no ALTER_CONFIGS for producer or consumer, and explicit group READ grants.
- The `apache/kafka` image bundles a JRE (Temurin 25 on trunk, see Q2), so Java4Shell matters here. The pinned digest must be an image rebuilt after the Temurin patch, or Kafka must be built on a patched JRE. Base64 decoding of untrusted input in Kafka is probably limited to auth paths (SCRAM/OAuth), but that was not verified.

### Gaps
- 4.1.0 release notes were not fetched. The commonly reported "KIP-932 preview in 4.1" is unverified here.
- The minimum Java version for 4.3/4.4 brokers was not found in the announcements. It was 17 as of 4.0.
- Whether the published `apache/kafka:4.4.0` digest already carries a Java4Shell-patched JRE could not be determined. It needs `docker run ... java -version` against the vendor advisory.
- There is no evidence on which Kafka code paths (if any) reach the vulnerable JDK Base64 decoder.

## 2. Official images (apache/kafka, apache/kafka-native): status, non-root/read-only, measured memory

### Takeaway
`apache/kafka` (JVM) is the production image. `apache/kafka-native` (GraalVM) is officially **experimental, dev/test only**, though it supports SASL from 4.4.0. Both run as a non-root `appuser` with no fixed UID. A read-only root needs writable mounts at least for `/opt/kafka/config`, the data dir and probably `/tmp` and the logs. The script defaults the heap to 1 GB, so it **must** be overridden under a 512-768 MB cap. Real measurements are sparse: about 300-400 MiB RSS for an idle or light JVM broker with a default 1 GB heap, growing to about 1.1 GiB under load. The native image measured about 230-250 MB max in its KIP benchmark.

### Cited Findings
- JVM images exist from 3.7.0. Native images exist from 3.8.0. The docs say the native image "is experimental and intended for local development and testing purposes only" and "it is not recommended for production use". It also says "The native image supports SASL authentication since 4.4.0; earlier native images do not." — [Kafka 4.4 Docker docs](https://kafka.apache.org/44/getting-started/docker/)
- KIP-974 (native image) says it "is recommended only for development, and testing and not for production workloads". Native-image "does not support dynamic class loading", and full reflection coverage can never be guaranteed. — [KIP-974](https://cwiki.apache.org/confluence/display/KAFKA/KIP-974:+Docker+Image+for+GraalVM+based+Native+Kafka+Broker)
- **KIP-974 benchmark** (older: 2023, Java 17.0.8, m6i.2xlarge; created a topic, produced and consumed with defaults; the memory metric is not defined): JVM broker about 1150-1200 ms startup and **about 1 GB max memory**. Native with serial GC: **about 250 MB** (no PGO) or **about 230 MB** (PGO). Native with G1: about 520-540 MB. — [KIP-974](https://cwiki.apache.org/confluence/display/KAFKA/KIP-974:+Docker+Image+for+GraalVM+based+Native+Kafka+Broker). GraalVM Community supports only serial GC, so the G1 rows likely do not apply to the official image (per the README, via search summary) — [docker/native README](https://apache.googlesource.com/kafka/+/refs/heads/trunk/docker/native/)
- A Red Hat talk (older, Ozan Günalp) gave kafka-native at about 45 MB RSS vs about 370 MB for a JVM Kafka test container. The slides say "This is not a benchmark". — [slides](https://www.slideshare.net/slideshow/running-kafka-as-a-native-binary-using-graalvm-with-ozan-gnalp/258205676)
- **Most recent JVM measurement found (Oct 2026, apache/kafka:4.3.1):** a single KRaft broker "used 402 MiB of RAM" (no heap override, so the 1 GB default). In a 3-broker cluster with `-Xms1g -Xmx1g`, each broker sat at about 300 MiB idle and grew to 1.1 GiB after a benchmark, as the heap filled. The measuring tool is not stated. — [ComputingForGeeks, updated 2026-10-18](https://computingforgeeks.com/deploy-kafka-docker-compose/)
- Default heap: `kafka-server-start.sh` exports `KAFKA_HEAP_OPTS="-Xmx1G -Xms1G"` when the variable is empty. — [kafka-server-start.sh](https://raw.githubusercontent.com/apache/kafka/trunk/bin/kafka-server-start.sh)
- Confluent's operator docs (vendor, different product) note that the default heap can equal 100% of the pod memory request, so heap must be pinned to leave room for non-heap memory. Seen via search summary only. — [Confluent operator resources](https://docs.confluent.io/operator/current/co-resources.md)
- **JVM Dockerfile (trunk)**: `ARG base_image=docker.io/library/eclipse-temurin:25-jre-alpine`. The user is created with `adduser ... appuser` (no explicit UID), then `USER appuser`. It creates `/var/lib/kafka/data`, `/etc/kafka/secrets`, `/etc/kafka/docker`, `/opt/kafka`, `/usr/logs` and `/mnt/shared/config`, with `chmod -R ug+w` on `/etc/kafka` and `/var/lib/kafka`. It declares `VOLUME ["/etc/kafka/secrets", "/var/lib/kafka/data", "/mnt/shared/config"]`, uses `CMD ["/etc/kafka/docker/run"]` and exposes 9092. — [docker/jvm/Dockerfile](https://raw.githubusercontent.com/apache/kafka/trunk/docker/jvm/Dockerfile)
- **Native Dockerfile (trunk)**: built from `ghcr.io/graalvm/graalvm-community:25`. The runtime base is **`alpine:latest`** (not pinned), with the same non-root `appuser`. A comment says GraalVM 25+ is required because earlier versions cause "intermittent segfaults (~2%) on startup". It patches libcrypto3/libssl3/zlib for CVE-2026-28390 and CVE-2026-22184. — [docker/native/Dockerfile](https://raw.githubusercontent.com/apache/kafka/trunk/docker/native/Dockerfile)
- The startup `configure` script checks that "path /opt/kafka/config/ writable" and that `CLUSTER_ID` is set in KRaft mode. It derives `KAFKA_LISTENERS` from `KAFKA_ADVERTISED_LISTENERS` by replacing the host with 0.0.0.0 when listeners are unset. — [docker/resources/common-scripts/configure](https://raw.githubusercontent.com/apache/kafka/trunk/docker/resources/common-scripts/configure)
- Config is passed as env vars (`KAFKA_*`) or as a properties file mounted at `/mnt/shared/config`. Env vars override the file. SSL files referenced by env vars must sit in `/etc/kafka/secrets`. SASL examples mount a JAAS file and point `KAFKA_OPTS` at it. — [docker/examples README](https://github.com/apache/kafka/blob/trunk/docker/examples/README.md)

### Inferences
- With `--read-only`, these need to be writable: tmpfs for `/opt/kafka/config` (the script requires it) and `/tmp`, a volume for `/var/lib/kafka/data`, and probably `/opt/kafka/logs` (Log4j2 file appenders) and `/mnt/shared/config` if used. This is untested. The `launch` script, which likely writes server.properties and formats storage, was not inspected. Expect one or two iterations to find all write paths, then lock them in with `tests/test_compose_hardening.py`.
- `appuser` has no fixed UID, and the UID can change between rebuilds. Pin `user:` in compose to the numeric UID found in the pinned digest, and chown the data volume to it.
- A reasonable starting point for the JVM image under a **768 MB cap** is about `-Xms256m -Xmx384m`, plus `-XX:MaxDirectMemorySize` and metaspace limits. The ~300-400 MiB measured RSS includes a mostly empty 1 GB heap, so a smaller heap at this load (≤ 2k msg/s, small records) should fit. This is an extrapolation and **must be measured** (`docker stats`, cgroup `memory.peak`) during a 100× replay.
- Container memory accounting includes page cache. Kafka relies on it, and it is reclaimable, so a cap mostly shrinks cache rather than OOM-killing. Heap + metaspace + direct buffers + thread stacks are the real hard floor.
- The native image would fit 512 MB easily, but it is labelled not-for-production by Apache. Using it in a "the senior reviewer can't find the shortcut" portfolio would itself be a shortcut. JVM + tuned heap is the defensible choice. Native could still be a documented measured comparison.

### Gaps
- No primary-source measurement of a 4.x JVM broker with a small heap (256-512 MB) under sustained load was found. A community ARMv7 image using `-Xms160m -Xmx160m` under a 256m limit exists, but it is not a benchmark ([Docker Hub](https://hub.docker.com/r/kaustubh456/kafka-armv7)).
- The released 4.4.0 image may use a different base or JRE than trunk. Check with `docker inspect` on the pinned digest.
- The content of the `launch` script (exact write paths, whether it runs `kafka-storage format` each start) was not retrieved.

## 3. Single-node KRaft configuration

### Takeaway
Use combined mode (`process.roles=broker,controller`), which Apache says is not for "critical deployment environments" but is fine here. Use a standalone-formatted single voter, and set **every internal topic's replication factor and min ISR to 1**: offsets, transaction state, share-coordinator state. Otherwise those topics fail to create, and transactions/EOS break silently on one broker.

### Cited Findings
- Combined mode: "Combined mode is not recommended in critical deployment environments". Controllers cannot be rolled or scaled separately. — [KRaft operations 4.4](https://kafka.apache.org/44/operations/kraft/)
- Every node must set `controller.quorum.bootstrap.servers`. With a dynamic quorum, `controller.quorum.voters` must not be set. A new cluster is bootstrapped with `kafka-storage.sh format --cluster-id <ID> --standalone --config ...`, which makes that node the sole voter. `kafka-features.sh describe` shows `kraft.version` (0 = static, ≥1 = dynamic). — [KRaft operations 4.4](https://kafka.apache.org/44/operations/kraft/)
- A working single-node compose (Oct 2026, apache/kafka:4.3.1) uses: `KAFKA_PROCESS_ROLES: broker,controller`, `KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER`, `KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:9093`, `KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1`, `KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1`, `KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1`, `KAFKA_SHARE_COORDINATOR_STATE_TOPIC_REPLICATION_FACTOR: 1`, `KAFKA_SHARE_COORDINATOR_STATE_TOPIC_MIN_ISR: 1`, `KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS: 0`, `KAFKA_LOG_DIRS: /var/lib/kafka/data`, and separate INTERNAL/EXTERNAL/CONTROLLER listeners. The defaults "would ask for three replicas, which one broker can't provide." — [ComputingForGeeks](https://computingforgeeks.com/deploy-kafka-docker-compose/)
- The Apache Docker example sets `KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1` "since the default would otherwise be 3". `CLUSTER_ID` has a default but should be set. — [docker/examples README](https://github.com/apache/kafka/blob/trunk/docker/examples/README.md)
- From 4.3, `num.partitions`/`default.replication.factor` apply consistently at topic creation (KIP-1211). — [Confluent 4.3 post](https://www.confluent.io/es-mx/blog/apache-kafka-4-3-release/)
- From 4.4, the broker must be ≥ the version of the tool that formatted the log dirs (KIP-1170). — [4.4.0 announcement](https://kafka.apache.org/blog/2026/10/22/apache-kafka-4.4.0-release-announcement/)

### Inferences
- Suggested settings for this project (not sourced as a recipe; built from the facts above):
  - `default.replication.factor=1` and `min.insync.replicas=1`. Producers use `acks=all` + `enable.idempotence=true`; acks=all is equivalent to acks=1 on one node but keeps the code production-shaped. `auto.create.topics.enable=false`, and topics are created by the admin principal.
  - For EOS on one node, `transaction.state.log.replication.factor=1` and `transaction.state.log.min.isr=1` are mandatory.
  - Retention: the replay is about 1M events (~few hundred MB at most), so set `log.retention.hours` or `retention.bytes` per topic to bound disk, with `log.segment.bytes` around 64-128 MB so retention can delete. The default is 1 GB segments, and on a small topic nothing would ever be deleted.
  - `num.partitions` = 3-6 for parallel consumers, not more. Each partition costs file handles and memory.
  - Prefer `controller.quorum.bootstrap.servers` + `--standalone` (dynamic quorum, the documented 4.x way) over the static `controller.quorum.voters` that most blog posts still show.
- Event volume: 187 events/s at 1× is about 19k/s at 100×. That is trivial for one broker on disk; the constraint is memory, not throughput.

### Gaps
- No primary Apache guidance specific to page-cache sizing for tiny brokers was found.

## 4. Security on one box: SASL/SCRAM vs mTLS vs PLAINTEXT, ACLs, per-client principals

### Takeaway
Apache says SCRAM and PLAIN "should be used only with TLS". On a box where the listener is bound only to 127.0.0.1 and the k3s bridge, SASL/SCRAM over PLAINTEXT gives authenticated per-client principals and ACLs, and leaves only a local-sniffing risk (needs root or CAP_NET_RAW on the host). mTLS or SASL_SSL is the textbook answer. Either way, use StandardAuthorizer, deny by default, and one principal each for producer, consumer, admin and the inter-broker/controller link.

### Cited Findings
- "SCRAM should be used only with TLS-encryption to prevent interception of SCRAM exchanges." Only SHA-256/SHA-512 are supported, with a minimum of 4096 iterations. — [SASL docs 4.4](https://kafka.apache.org/44/security/authentication-using-sasl/)
- In KRaft, "Credentials for inter-broker communication must be created before Kafka brokers are started". `kafka-storage.sh` can format with `--add-scram 'SCRAM-SHA-256=[name="admin",password="..."]'`. SCRAM credentials live in the metadata log, which is "suitable for production use in installations where KRaft controllers are secure and on a private network". — [SASL docs 4.4](https://kafka.apache.org/44/security/authentication-using-sasl/)
- "SASL/PLAIN should be used only with SSL as transport layer". The default PLAIN implementation stores clear passwords in the JAAS file. — [SASL docs 4.4](https://kafka.apache.org/44/security/authentication-using-sasl/)
- CVE-2024-56128 (older): SCRAM without TLS was replayable because the nonce was not validated. It was fixed in 3.9.0, so 4.x is not affected. — [Kafka CVE list](https://kafka.apache.org/community/cve-list/)
- Authorization CVEs that make ACL design matter: CVE-2026-112375 (unauthorized principal reads broker files/env via IncrementalAlterConfigs) and CVE-2026-41115 (group describe checks DESCRIBE, not READ; no fixed release listed). — [Kafka CVE list](https://kafka.apache.org/community/cve-list/)
- The official image supports SASL and SSL via a mounted JAAS file + `KAFKA_OPTS` and secrets in `/etc/kafka/secrets`. The native image supports SASL only from 4.4.0. — [docker/examples README](https://github.com/apache/kafka/blob/trunk/docker/examples/README.md), [Kafka 4.4 Docker docs](https://kafka.apache.org/44/getting-started/docker/)

### Inferences
- Defensible pattern for this project:
  - Listeners: `CONTROLLER` (SASL_PLAINTEXT or PLAINTEXT, bound to 127.0.0.1 inside the container network, never published), `INTERNAL`/`HOST` on 127.0.0.1, and `PODS` on the k3s bridge address. All client listeners SASL_SCRAM-SHA-512. Optionally make them SASL_SSL with a self-signed CA if the extra memory and complexity is accepted. TLS on the JVM costs some CPU and heap, but not much at 2k msg/s.
  - `authorizer.class.name=org.apache.kafka.metadata.authorizer.StandardAuthorizer`, `allow.everyone.if.no.acl.found=false`, `super.users=User:admin;User:broker` (the broker/controller principal needs super-user or cluster ACLs).
  - Principals: `producer` (WRITE + DESCRIBE on the transactions topic; IDEMPOTENT_WRITE / TransactionalId WRITE if using EOS), `consumer` (READ on topic + READ on its group), `admin` (create/alter topics, used only by setup jobs), plus Prometheus-exporter (DESCRIBE on topics/groups).
  - SCRAM passwords are bootstrapped with `--add-scram` at format time, kept in `.secrets/` and registered in `secrets_registry.py`, with the k8s client's credential as a Kubernetes Secret, the same pattern as Redis (`graphguard-redis`).
- This mirrors what the project already did for Redis (per-user ACLs, default user off), so it is consistent and easy to explain in an interview.
- No sources were found describing "what real small deployments do". Most single-node blog setups (e.g. ComputingForGeeks) run full PLAINTEXT with no auth.

### Gaps
- StandardAuthorizer docs were not fetched directly. The class name and `super.users` semantics above come from prior knowledge of Kafka 3.x/4.x and should be checked against the 4.4 security docs.
- No measurement of the memory or CPU cost of TLS on a small broker was found.

## 5. Docker + k3s on the same host: listener and networking pitfalls

### Takeaway
The classic failure is `advertised.listeners`. A client bootstraps fine, then gets told to connect to an address it cannot reach (container hostname, 127.0.0.1, or 0.0.0.0). With host-local clients plus k3s pods, use **one listener per network**, each advertising the address that network's clients can reach. This project already solved the same problem for Redis with the k3s bridge `10.42.0.1` and a DNAT-aware NetworkPolicy.

### Cited Findings
- The Apache image derives `KAFKA_LISTENERS` from `KAFKA_ADVERTISED_LISTENERS` by rewriting the host to 0.0.0.0 when listeners are unset. That would bind every interface, so listeners must be set explicitly. — [configure script](https://raw.githubusercontent.com/apache/kafka/trunk/docker/resources/common-scripts/configure), [docker/examples README](https://github.com/apache/kafka/blob/trunk/docker/examples/README.md)
- A typical 2026 single-node compose uses separate `INTERNAL://kafka:19092` (container network) and `EXTERNAL://${HOST_IP}:9092` advertised listeners. — [ComputingForGeeks](https://computingforgeeks.com/deploy-kafka-docker-compose/)
- 4.4 adds KIP-1242: clients send cluster and node info on connect so **misrouted connections are detected**. This helps diagnose wrong-advertised-address bugs. — [4.4.0 announcement](https://kafka.apache.org/blog/2026/10/22/apache-kafka-4.4.0-release-announcement/)
- Project precedent (local repo): Redis publishes `127.0.0.1:6380:6379` and `10.42.0.1:6380:6379`. "10.42.0.1 is cni0, a private bridge: pods on 10.42.0.0/24 can reach it". `tests/test_compose_hardening.py` allows host bindings starting with `127.0.0.1` or `10.42.0.1` only. The NetworkPolicy has to allow the **post-DNAT** Docker address (`172.25.0.0/16:6379`), because Docker rewrites `10.42.0.1:6380` before the policy is evaluated. — `/srv/graphguard/docker-compose.yml` (lines ~167-174), `/srv/graphguard/k8s/networkpolicy.yaml` (~105-108), `/srv/graphguard/tests/test_compose_hardening.py:50`

### Inferences
- Kafka-specific version of that pattern:
  - `listeners=HOST://0.0.0.0:19092,PODS://0.0.0.0:19093,CONTROLLER://127.0.0.1:9093` inside the container.
  - Compose `ports: ["127.0.0.1:9092:19092", "10.42.0.1:9094:19093"]`.
  - `advertised.listeners=HOST://127.0.0.1:9092,PODS://10.42.0.1:9094`.
  - Host processes use :9092 and pods use 10.42.0.1:9094. Each listener advertises the address and **host** port its clients see, not the container port.
- The NetworkPolicy egress for the pod consumer must allow the Docker-network CIDR on the **container** port (19093), not 10.42.0.1:9094. This is the same DNAT trap already found with Redis.
- 10.42.0.1 exists only while k3s/cni0 is up. If Docker starts before cni0 exists, the port bind fails and the container will not start, the same dependency the Redis service already has. Note it in the runbook.
- The `GRAPHGUARD-EDGE` chain drops k3s ports on eth0. Since the Kafka bindings are not on eth0 they are not public, but `just edge-baseline` / `edge-status` should be re-run after adding listeners.
- With `CONTROLLER` bound to loopback inside the container, it is never reachable from pods. Pods also need nothing but the PODS listener.
- Phase 5 found Ray Serve HTTP saturates at about 200 tx/s, and the plan says the consumer scores in process. So the k3s pod running the consumer is a long-lived client and should use the KIP-848 protocol (`group.protocol=consumer`) if the client library supports it.

### Gaps
- No external article specifically covering "host-Docker Kafka reached from k3s pods" was found. The design above is extrapolated from the project's own Redis solution and Kafka listener semantics.

## 6. Alternatives in Nov 2026: Redpanda, AutoMQ, Bufstream, Tansu, WarpStream

### Takeaway
None of them is a better fit for a 512-768 MB, single-box, hire-me portfolio. **Redpanda 26.3.1 (released 20 Nov 2026) ended source availability.** The new Community Edition is free binaries under a 50-core-per-organization licence. Bufstream and WarpStream are object-storage designs sized for clusters (Bufstream recommends 8 GiB per replica). Tansu is interesting but immature and single-maintainer. Apache Kafka 4.4 is still the right pick: it is the name hiring managers search for, it is Apache-2.0, and the JVM fits with a tuned heap.

### Cited Findings
- Redpanda (vendor statements): "Redpanda Streaming/Operator will no longer be source available starting with 26.3.1". 26.3.1 is "available on November 20". The Community Edition stays free up to "50 cores in total per organization or legal entity, not per cluster". Clusters over the limit keep running, but in-place upgrades are blocked. Redpanda Connect and Console "remain source-available". Post dated 12 Nov 2026. — [Redpanda R2 blog](https://www.redpanda.com/blog/r2-the-engine-of-engines)
  - Conflict: Redpanda's licensing docs pages still describe the Community Edition as BSL (source-available), so the docs lag the announcement. — [Redpanda licensing overview](https://docs.redpanda.com/current/get-started/licensing/overview/)
- Note for this project: CLAUDE.md records that Phase 6 already switched from Redpanda to Kafka 4. — `/srv/graphguard/CLAUDE.md` (phase table)
- Bufstream (vendor docs): recommends 3 replicas at a minimum of **2 cores and 8 GiB each**, with 6 replicas across AZs advised, and a 1:4 vCPU:GiB ratio. It has no local disk, and I/O goes over the network to object storage. — [Bufstream cluster recommendations](https://buf.build/docs/bufstream/deployment/cluster-recommendations)
- AutoMQ: describes itself as Apache-2.0, a diskless Kafka fork on object storage (vendor claim). No official minimum-memory figure was found. — [AutoMQ blog](https://www.automq.com/blog/automq-vs-warpstream-diskless-kafka-platforms-compared)
- WarpStream: a BYOC model where agents run in the customer VPC against object storage. No self-hosted footprint figure was found (vendor/competitor blogs only). — [AutoMQ vs WarpStream (competitor blog)](https://www.automq.com/blog/automq-vs-warpstream-diskless-kafka-platforms-compared)
- Tansu: a Rust, "stateless Kafka-compatible broker with pluggable storage (PostgreSQL, SQLite, S3, memory)", consensus-free, built solo for about two years (presented at QCon London 2026). It can write schema-backed topics as Iceberg/Delta tables. Crate version 0.6.0. The licence is inconsistent: the README says AGPL, crates.io says Apache-2.0. A fork/rename "Nisshi" exists. — [tansu-io/tansu](https://github.com/tansu-io/tansu), [InfoQ Mar 2026](https://infoq.com/news/2026/03/tansu-stateless-kafka-compatible), [docs.rs](https://docs.rs/crate/tansu/0.6.0/source/README.md), [Nisshi README](https://raw.githubusercontent.com/nisshi-io/nisshi/main/README.md)

### Inferences
- Redpanda would fit memory better (C++, no JVM). But as of 26.3.1 new versions are closed-source, and the last source-available version would freeze, which is a weak story for a public, security-conscious repo. The earlier R-2 decision to use Kafka 4 holds up better now than when it was made.
- Tansu's Iceberg sink overlaps nicely with the project's lakehouse, but a single-maintainer 0.x broker is a risk the "senior reviewer" bar would flag. It is at most a footnote.
- Object-storage designs (Bufstream, WarpStream, AutoMQ) trade local disk for S3 latency and per-request cost, and are aimed at multi-AZ clusters. That is the wrong shape for one box.

### Gaps
- No measured memory numbers were found for Redpanda dev-mode, AutoMQ single-node or Tansu, so a like-for-like footprint comparison is not possible from sources.
- The exact text of the new Redpanda Community Edition licence was not read.

## 7. Cheap monitoring of a single broker

### Takeaway
Consumer group lag, the metric that matters for a replay pipeline, does **not** come from the broker's JMX. Use a small Admin-API exporter (danielqsj `kafka_exporter`, Go) for lag and topic offsets. Add the Prometheus JMX exporter javaagent only if broker internals are needed, with a strict MBean allow-list, because it runs inside the broker JVM and spends its memory budget.

### Cited Findings
- The JMX exporter runs as a Java agent inside the broker JVM. KAFKA-9794 (open) reports CPU and memory rising sharply in Docker after enabling it, with no figures. Guides recommend limiting the MBeans queried. — [KAFKA-9794 (mail archive)](https://mail-archive.com/jira@kafka.apache.org/msg36977.html), [OneUptime Jan 2026](https://oneuptime.com/blog/post/2026-01-24-monitor-kafka-jmx-metrics/view)
- JMX gives the per-consumer client metric `records-lag`, not group lag. kafka_exporter reads group offsets and exposes `kafka_consumergroup_lag{consumergroup,topic,partition}`. Burrow and kafka-lag-exporter are alternatives. — [OneUptime Prometheus/Grafana guide](https://oneuptime.com/blog/post/2026-01-21-kafka-monitoring-prometheus-grafana/view), [DZone](https://dzone.com/articles/kafka-monitoring-via-prometheus-amp-grafana)
- 4.4 exposes Linux process I/O metrics (`/proc/self/io`) via JMX (KIP-1291). 4.3 added per-partition retention-usage metrics (KIP-1257). 4.2 added share-group lag metrics. — [4.4.0 announcement](https://kafka.apache.org/blog/2026/10/22/apache-kafka-4.4.0-release-announcement/), [Confluent 4.3 post](https://www.confluent.io/es-mx/blog/apache-kafka-4-3-release/), [4.2.0 announcement](https://kafka.apache.org/blog/2026/02/17/apache-kafka-4.2.0-release-announcement/)
- The image's `configure` script validates `KAFKA_JMX_OPTS`/`KAFKA_OPTS` (it requires the `com.sun.management.jmxremote.rmi.port` property when JMX is enabled). — [configure script](https://raw.githubusercontent.com/apache/kafka/trunk/docker/resources/common-scripts/configure)

### Inferences
- The cheapest useful setup:
  - `kafka_exporter` as its own capped container (~32-64 MB cap, to be measured), authenticating as a `monitor` SCRAM principal with DESCRIBE-only ACLs, port on 127.0.0.1.
  - The consumer itself exports lag and processing latency (it already must, for the p99 story).
  - Broker health from `docker stats`/cgroup memory, plus the existing health-check pattern (a `just kafka-status` that fails on lag above a threshold or a broker down).
  - Skip the JMX agent unless a specific broker metric is needed. If added, budget about 30-60 MB of extra heap/metaspace (unmeasured guess, so measure it).
- There is no Prometheus server in GraphGuard yet (LuBot's Grafana/Prometheus are off-limits). Lag can initially be scraped ad hoc or written by the consumer to MLflow/JSON. A full Prometheus belongs to Phase 8 monitoring.

### Gaps
- No measured memory cost was found for the JMX exporter agent or for kafka_exporter on a small broker.
- kafka_exporter's support for KIP-848 groups and SCRAM-SHA-512 in its 2026 release was not verified.
