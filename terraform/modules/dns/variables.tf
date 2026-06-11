variable "domain_name" {
  description = "Registered apex domain (e.g. example.dev). The zone NS records must be set on the registrar after first apply."
  type        = string
}
