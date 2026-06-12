variable "name" {
  description = "Guardrail name"
  type        = string
}

variable "blocked_message" {
  description = "Bedrock's blocked-content message (the agent overrides it with a polite decline; never shown)"
  type        = string
  default     = "I can only help with refrigerator and dishwasher parts."
}

variable "pii_entities" {
  description = "PII entity types to anonymize (NFR-13)"
  type        = list(string)
  default     = ["EMAIL", "PHONE", "CREDIT_DEBIT_CARD_NUMBER", "US_SOCIAL_SECURITY_NUMBER"]
}
