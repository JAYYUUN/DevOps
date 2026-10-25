{{/* External Ingress controllers need explicit certificate Secret references.
     The upstream shared-secrets Job still generates the wildcard Secret. */}}
{{- define "webservice.tlsSecret" -}}
{{- printf "%s-wildcard-tls" .root.Release.Name -}}
{{- end -}}
{{- define "registry.tlsSecret" -}}
{{- printf "%s-wildcard-tls" .Release.Name -}}
{{- end -}}
