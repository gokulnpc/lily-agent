# bootstrap — Terraform state bucket

One-time stack that creates the S3 bucket all other stacks use as their remote
state backend. Uses **local state** (gitignored) on purpose — there is nothing
to store remote state in yet.

## Procedure (apply exactly once)

```sh
cd terraform/bootstrap
terraform init
terraform apply        # requires explicit owner confirmation per CLAUDE.md
terraform output state_bucket_name
```

Paste the bucket name into the `backend "s3"` block of:
- `terraform/envs/dev/infra/backend.tf`
- `terraform/envs/dev/platform/backend.tf`

Locking uses Terraform ≥ 1.10 S3-native lockfiles (`use_lockfile = true`) —
no DynamoDB table.

The bucket name embeds a random suffix (not the account ID — account IDs are
never committed). `prevent_destroy` is set; deleting this bucket means losing
all infra state.

## Recorded bucket name

Filled in after the one-time apply:

- `state_bucket_name`: `lily-tfstate-a2b0623e` (applied 2026-06-11)
