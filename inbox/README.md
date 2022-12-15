# INBOX SETUP

### Setup IAM user with SES Sending permissions

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": "ses:SendRawEmail",
            "Resource": "*"
        }
    ]
}
```



#### Store credentials in settings.core.email

```
SES_ACCESS_KEY = "***"
SES_SECRET_KEY = "***"
SES_REGION = "us-east-1"

EMAIL_USE_TLS = True
EMAIL_HOST = 'email-smtp.us-east-1.amazonaws.com'
EMAIL_HOST_USER = '***'
EMAIL_HOST_PASSWORD = '***'
EMAIL_PORT = 587
```



### Goto AWS SES Admin

DNS Records needs to include



| Type | Name           | Priority | Value                                         |
| :--- | :------------- | -------- | :-------------------------------------------- |
| MX   | mail.payomi.io | 10       | **feedback**-smtp.us-east-1.amazon**ses**.com |
| MX   | @              | 10       | **inbound**-smtp.us-east-1.amazon**aws**.com  |
| TXT  | mail.payomi.io |          | "v=spf1 include:amazonses.com ~all"           |



### Goto AWS SNS Admin
