{{- define "cicd.name" -}}
{{- printf "%s-link" .Release.Name | trunc 50 | trimSuffix "-" -}}
{{- end -}}
{{- define "cicd.owner" -}}
{{- printf "%s.%s" .Release.Namespace .Release.Name | trunc 63 | trimSuffix "." -}}
{{- end -}}
