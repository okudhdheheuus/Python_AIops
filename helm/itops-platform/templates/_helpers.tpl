{{- define "itops.fullname" -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "itops.postgres-url" -}}
postgresql+asyncpg://{{ .Values.postgres.auth.username }}:{{ .Values.postgres.auth.password }}@{{ include "itops.fullname" . }}-postgres:5432/{{ .Values.postgres.auth.database }}
{{- end -}}