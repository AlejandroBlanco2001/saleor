# sqs

One standard SQS queue, used as the Celery broker for the locally-run
monolith (step 7's `monolith` Compose profile). No FIFO needed, default
visibility timeout is fine for a course lab.

No dependency on any other module.

**Unverified assumption** (see root README): this assumes the Learner Lab's
`LabRole`/`LabInstanceProfile` actually grants SQS permissions. Not something
this module can check — verify with `aws iam list-attached-role-policies
--role-name LabRole` before relying on it.

## Inputs

| Name | Description | Type |
|---|---|---|
| `project_name` | Short name used to tag/name resources. | `string` |

## Outputs

| Name | Description |
|---|---|
| `queue_url` | Full queue URL — this is what goes into `CELERY_BROKER_URL=sqs://...`, not the ARN. |
| `queue_arn` | Queue ARN, for reference/IAM policy authoring if that's ever needed. |
