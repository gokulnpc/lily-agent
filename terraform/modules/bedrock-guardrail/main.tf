# Bedrock Guardrail (D6): the prompt-attack + PII layer of the guardrail chain.
# Scope-gating is the Haiku scope classifier's job (in app code) — it is the
# accurate scope arbiter; a Bedrock topic policy was tried and dropped because it
# false-positived on legitimate brand+model part questions. Bedrock here does the
# two things it does irreplaceably: detect prompt-injection and anonymize PII. The
# deterministic part-number validator is the third layer. The agent never shows
# blocked_*_messaging — it substitutes a polite in-voice decline — but Bedrock
# requires the fields.

resource "aws_bedrock_guardrail" "this" {
  name                      = var.name
  description               = "Lily input/output guardrail: block prompt-injection, anonymize PII (scope is the Haiku gate's job)."
  blocked_input_messaging   = var.blocked_message
  blocked_outputs_messaging = var.blocked_message

  # Prompt-injection / jailbreak detection on the user input (PROMPT_ATTACK is
  # input-only; output_strength must be NONE).
  content_policy_config {
    filters_config {
      type            = "PROMPT_ATTACK"
      input_strength  = "HIGH"
      output_strength = "NONE"
    }
  }

  # Mask PII (NFR-13). ANONYMIZE (not BLOCK) so order lookups still work: the
  # deterministic order tool reads the order#/email resolved before the guardrail,
  # while the LLM and the rendered response only ever see masked values.
  sensitive_information_policy_config {
    dynamic "pii_entities_config" {
      for_each = toset(var.pii_entities)
      content {
        type   = pii_entities_config.value
        action = "ANONYMIZE"
      }
    }
  }
}

# Publish an immutable version for the orchestrator to pin (the app defaults to
# DRAFT for dev; prod sets LILY_GUARDRAIL_VERSION to this). Re-cut whenever the
# guardrail config changes (the guardrail's `version` attribute bumps on update)
# so the pinned version never drifts from the live policy.
resource "aws_bedrock_guardrail_version" "this" {
  guardrail_arn = aws_bedrock_guardrail.this.guardrail_arn
  description   = "Published version pinned by the orchestrator."

  lifecycle {
    replace_triggered_by = [aws_bedrock_guardrail.this.version]
  }
}
