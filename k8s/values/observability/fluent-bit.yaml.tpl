# Fluent Bit DaemonSet (Phase 4). Tails container logs, keeps our already-JSON
# log lines (trace_id/session_id/service), and ships them to the SHARED
# OpenSearch domain via SigV4 (IRSA) into the lily-logs-* namespace ONLY (NFR-19,
# D10). Rendered by Terraform (templatefile): ${opensearch_host}, ${role_arn}.

serviceAccount:
  create: true
  name: fluent-bit
  annotations:
    eks.amazonaws.com/role-arn: ${role_arn}

# DaemonSet on every node, including the spot (stateless) pool.
tolerations:
  - operator: Exists

resources:
  requests:
    cpu: 25m
    memory: 64Mi

config:
  service: |
    [SERVICE]
        Daemon Off
        Flush 5
        Log_Level info
        Parsers_File /fluent-bit/etc/parsers.conf
        HTTP_Server On
        HTTP_Listen 0.0.0.0
        HTTP_Port 2020

  inputs: |
    [INPUT]
        Name tail
        Path /var/log/containers/*.log
        multiline.parser docker, cri
        Tag kube.*
        Mem_Buf_Limit 16MB
        Skip_Long_Lines On

  filters: |
    [FILTER]
        Name kubernetes
        Match kube.*
        Merge_Log On
        Keep_Log Off
        K8S-Logging.Parser On
        K8S-Logging.Exclude On
    # Ship only the Lily APP namespaces — not all of kube-system, and NOT
    # observability itself (that would re-ingest Fluent Bit's own logs in a loop).
    # Keeps the small dev OpenSearch domain off the 429 throttle and the index
    # scoped to what we query. Our app logs are JSON, so Merge_Log lifts
    # trace_id/session_id/intent to the ROOT of the doc (NFR-19, Kibana-queryable).
    [FILTER]
        Name grep
        Match kube.*
        Regex $kubernetes['namespace_name'] ^(agent|frontend|data|commerce)$

  # Bulk writes go to /_bulk (domain-root); the index is lily-logs-<date>. The
  # IRSA policy grants POST /_bulk + management of lily-logs-* only.
  outputs: |
    [OUTPUT]
        Name opensearch
        Match kube.*
        Host ${opensearch_host}
        Port 443
        TLS On
        AWS_Auth On
        AWS_Region us-east-1
        Logstash_Format On
        Logstash_Prefix lily-logs
        Suppress_Type_Name On
        Replace_Dots On
        Retry_Limit 5
