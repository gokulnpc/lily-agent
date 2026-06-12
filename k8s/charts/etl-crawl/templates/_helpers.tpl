{{- define "etl-crawl.name" -}}
{{- .Chart.Name -}}
{{- end -}}

{{- define "etl-crawl.labels" -}}
app.kubernetes.io/name: {{ include "etl-crawl.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}
