# One-time: adopt the hosted zone auto-created when lily-agent.com was
# registered in Route53, instead of creating a parallel zone and re-delegating
# NS at the registrar. Remove this file once the import has applied.
import {
  to = module.dns.aws_route53_zone.this
  id = "Z03433702JD3UKK1GTRIZ"
}
