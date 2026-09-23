Lamda

import boto3
import json
import os
import textwrap
from datetime import date, datetime, timedelta
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


# ============================================================
# CONFIGURATION
# ============================================================

AWS_REGION = "us-east-1"

SENDER_EMAIL = "kadiyalanandini666@gmail.com"
RECIPIENT_EMAIL = "kadiyalanandini666@gmail.com"

SNS_TOPIC_ARN = (
    "arn:aws:sns:us-east-1:190535468276:aws-cost-audit-notification"
)

PDF_PATH = "/tmp/aws-cost-audit-report.pdf"


# ============================================================
# AWS CLIENTS
# ============================================================

ec2 = boto3.client(
    "ec2",
    region_name=AWS_REGION
)

s3 = boto3.client(
    "s3",
    region_name=AWS_REGION
)

iam = boto3.client(
    "iam",
    region_name=AWS_REGION
)

ce = boto3.client(
    "ce",
    region_name=AWS_REGION
)

ses = boto3.client(
    "ses",
    region_name=AWS_REGION
)

sns = boto3.client(
    "sns",
    region_name=AWS_REGION
)


# ============================================================
# EC2
# ============================================================

def collect_ec2():

    instances = []

    paginator = ec2.get_paginator(
        "describe_instances"
    )

    for page in paginator.paginate():

        for reservation in page["Reservations"]:

            for instance in reservation["Instances"]:

                tags = {
                    tag["Key"]: tag["Value"]
                    for tag in instance.get("Tags", [])
                }

                instances.append({
                    "InstanceId":
                        instance["InstanceId"],

                    "InstanceType":
                        instance["InstanceType"],

                    "State":
                        instance["State"]["Name"],

                    "AvailabilityZone":
                        instance.get(
                            "Placement", {}
                        ).get(
                            "AvailabilityZone"
                        ),

                    "LaunchTime":
                        str(
                            instance.get(
                                "LaunchTime"
                            )
                        ),

                    "PrivateIp":
                        instance.get(
                            "PrivateIpAddress"
                        ),

                    "PublicIp":
                        instance.get(
                            "PublicIpAddress"
                        ),

                    "Tags":
                        tags
                })

    return instances


# ============================================================
# S3
# ============================================================

def collect_s3():

    buckets = []

    response = s3.list_buckets()

    for bucket in response["Buckets"]:

        name = bucket["Name"]

        # Region
        try:

            location = s3.get_bucket_location(
                Bucket=name
            )

            region = location.get(
                "LocationConstraint"
            )

            if region is None:
                region = "us-east-1"

        except Exception as e:

            region = f"ERROR: {str(e)}"

        # Versioning
        try:

            versioning = s3.get_bucket_versioning(
                Bucket=name
            )

            versioning_status = versioning.get(
                "Status",
                "Disabled"
            )

        except Exception:

            versioning_status = "Unknown"

        # Lifecycle
        try:

            lifecycle = (
                s3.get_bucket_lifecycle_configuration(
                    Bucket=name
                )
            )

            lifecycle_rules = len(
                lifecycle.get(
                    "Rules",
                    []
                )
            )

        except Exception:

            lifecycle_rules = 0

        # Tags
        try:

            tag_response = s3.get_bucket_tagging(
                Bucket=name
            )

            tags = {
                tag["Key"]: tag["Value"]
                for tag in tag_response.get(
                    "TagSet",
                    []
                )
            }

        except Exception:

            tags = {}

        buckets.append({

            "BucketName":
                name,

            "CreationDate":
                str(
                    bucket["CreationDate"]
                ),

            "Region":
                region,

            "Versioning":
                versioning_status,

            "LifecycleRules":
                lifecycle_rules,

            "Tags":
                tags
        })

    return buckets


# ============================================================
# IAM USERS
# ============================================================

def collect_iam_users():

    users = []

    paginator = iam.get_paginator(
        "list_users"
    )

    for page in paginator.paginate():

        for user in page["Users"]:

            users.append({

                "UserName":
                    user["UserName"],

                "UserId":
                    user["UserId"],

                "Arn":
                    user["Arn"],

                "CreateDate":
                    str(
                        user["CreateDate"]
                    )
            })

    return users


# ============================================================
# IAM ROLES
# ============================================================

def collect_iam_roles():

    roles = []

    paginator = iam.get_paginator(
        "list_roles"
    )

    for page in paginator.paginate():

        for role in page["Roles"]:

            roles.append({

                "RoleName":
                    role["RoleName"],

                "RoleId":
                    role["RoleId"],

                "Arn":
                    role["Arn"],

                "CreateDate":
                    str(
                        role["CreateDate"]
                    )
            })

    return roles


# ============================================================
# IAM GROUPS
# ============================================================

def collect_iam_groups():

    groups = []

    paginator = iam.get_paginator(
        "list_groups"
    )

    for page in paginator.paginate():

        for group in page["Groups"]:

            groups.append({

                "GroupName":
                    group["GroupName"],

                "GroupId":
                    group["GroupId"],

                "Arn":
                    group["Arn"]
            })

    return groups


# ============================================================
# IAM POLICIES
# ============================================================

def collect_iam_policies():

    policies = []

    paginator = iam.get_paginator(
        "list_policies"
    )

    for page in paginator.paginate(
        Scope="Local"
    ):

        for policy in page["Policies"]:

            policies.append({

                "PolicyName":
                    policy["PolicyName"],

                "PolicyId":
                    policy["PolicyId"],

                "Arn":
                    policy["Arn"],

                "DefaultVersionId":
                    policy["DefaultVersionId"]
            })

    return policies


# ============================================================
# COST EXPLORER
# ============================================================

def collect_costs():

    end = date.today()

    start = end - timedelta(
        days=90
    )

    response = ce.get_cost_and_usage(

        TimePeriod={
            "Start":
                start.isoformat(),

            "End":
                end.isoformat()
        },

        Granularity="MONTHLY",

        Metrics=[
            "UnblendedCost"
        ],

        GroupBy=[
            {
                "Type":
                    "DIMENSION",

                "Key":
                    "SERVICE"
            }
        ]
    )

    costs = []

    for result in response[
        "ResultsByTime"
    ]:

        period = result[
            "TimePeriod"
        ]

        for group in result[
            "Groups"
        ]:

            costs.append({

                "Start":
                    period["Start"],

                "End":
                    period["End"],

                "Service":
                    group["Keys"][0],

                "Cost":
                    float(
                        group[
                            "Metrics"
                        ][
                            "UnblendedCost"
                        ][
                            "Amount"
                        ]
                    )
            })

    return costs


# ============================================================
# PDF ESCAPING
# ============================================================

def escape_pdf(text):

    return (
        str(text)
        .replace(
            "\\",
            "\\\\"
        )
        .replace(
            "(",
            "\\("
        )
        .replace(
            ")",
            "\\)"
        )
    )


# ============================================================
# PDF GENERATOR
# ============================================================

def create_pdf(report, filename):

    pages = []

    current_page = []

    # --------------------------------------------------------
    # Page helpers
    # --------------------------------------------------------

    def add_line(text=""):

        current_page.append(
            text
        )

        if len(current_page) >= 48:

            pages.append(
                current_page.copy()
            )

            current_page.clear()

    def add_wrapped(text):

        wrapped = textwrap.wrap(
            str(text),
            width=92
        )

        if not wrapped:
            wrapped = [""]

        for line in wrapped:
            add_line(line)

    # --------------------------------------------------------
    # TITLE
    # --------------------------------------------------------

    add_line(
        "AWS COST & RESOURCE AUDIT REPORT"
    )

    add_line(
        "=" * 92
    )

    add_line(
        f"Generated: {datetime.utcnow()} UTC"
    )

    add_line()

    # --------------------------------------------------------
    # ACCOUNT
    # --------------------------------------------------------

    add_line(
        "ACCOUNT SUMMARY"
    )

    add_line(
        "-" * 92
    )

    add_line(
        f"Account ID: {report['account']['AccountId']}"
    )

    add_line(
        f"Report Period: Last 90 Days"
    )

    add_line()

    # --------------------------------------------------------
    # EC2
    # --------------------------------------------------------

    add_line(
        "EC2 INVENTORY"
    )

    add_line(
        "-" * 92
    )

    ec2_instances = report["ec2"]

    add_line(
        f"Total Instances: {len(ec2_instances)}"
    )

    running = sum(
        1
        for i in ec2_instances
        if i["State"] == "running"
    )

    stopped = sum(
        1
        for i in ec2_instances
        if i["State"] == "stopped"
    )

    add_line(
        f"Running: {running}"
    )

    add_line(
        f"Stopped: {stopped}"
    )

    add_line()

    for instance in ec2_instances:

        add_wrapped(
            f"Instance: {instance['InstanceId']}"
        )

        add_wrapped(
            f"  Type: {instance['InstanceType']}"
        )

        add_wrapped(
            f"  State: {instance['State']}"
        )

        add_wrapped(
            f"  AZ: {instance['AvailabilityZone']}"
        )

        add_wrapped(
            f"  Launch: {instance['LaunchTime']}"
        )

        add_wrapped(
            f"  Private IP: {instance['PrivateIp']}"
        )

        add_wrapped(
            f"  Public IP: {instance['PublicIp']}"
        )

        add_wrapped(
            f"  Tags: {instance['Tags']}"
        )

        add_line()

    # --------------------------------------------------------
    # S3
    # --------------------------------------------------------

    add_line(
        "S3 INVENTORY"
    )

    add_line(
        "-" * 92
    )

    buckets = report["s3"]

    add_line(
        f"Total Buckets: {len(buckets)}"
    )

    add_line()

    for bucket in buckets:

        add_wrapped(
            f"Bucket: {bucket['BucketName']}"
        )

        add_wrapped(
            f"  Region: {bucket['Region']}"
        )

        add_wrapped(
            f"  Created: {bucket['CreationDate']}"
        )

        add_wrapped(
            f"  Versioning: {bucket['Versioning']}"
        )

        add_wrapped(
            f"  Lifecycle Rules: "
            f"{bucket['LifecycleRules']}"
        )

        add_wrapped(
            f"  Tags: {bucket['Tags']}"
        )

        add_line()

    # --------------------------------------------------------
    # IAM
    # --------------------------------------------------------

    iam_data = report["iam"]

    add_line(
        "IAM USERS"
    )

    add_line(
        "-" * 92
    )

    add_line(
        f"Total Users: "
        f"{len(iam_data['users'])}"
    )

    for user in iam_data["users"]:

        add_wrapped(
            f"User: {user['UserName']}"
        )

        add_wrapped(
            f"  User ID: {user['UserId']}"
        )

        add_wrapped(
            f"  ARN: {user['Arn']}"
        )

        add_wrapped(
            f"  Created: {user['CreateDate']}"
        )

        add_line()

    add_line(
        "IAM ROLES"
    )

    add_line(
        "-" * 92
    )

    add_line(
        f"Total Roles: "
        f"{len(iam_data['roles'])}"
    )

    for role in iam_data["roles"]:

        add_wrapped(
            f"Role: {role['RoleName']}"
        )

        add_wrapped(
            f"  Role ID: {role['RoleId']}"
        )

        add_wrapped(
            f"  ARN: {role['Arn']}"
        )

        add_wrapped(
            f"  Created: {role['CreateDate']}"
        )

        add_line()

    add_line(
        "IAM GROUPS"
    )

    add_line(
        "-" * 92
    )

    add_line(
        f"Total Groups: "
        f"{len(iam_data['groups'])}"
    )

    for group in iam_data["groups"]:

        add_wrapped(
            f"Group: {group['GroupName']}"
        )

        add_wrapped(
            f"  Group ID: {group['GroupId']}"
        )

        add_wrapped(
            f"  ARN: {group['Arn']}"
        )

        add_line()

    add_line(
        "IAM CUSTOMER-MANAGED POLICIES"
    )

    add_line(
        "-" * 92
    )

    add_line(
        f"Total Policies: "
        f"{len(iam_data['policies'])}"
    )

    for policy in iam_data["policies"]:

        add_wrapped(
            f"Policy: {policy['PolicyName']}"
        )

        add_wrapped(
            f"  Policy ID: {policy['PolicyId']}"
        )

        add_wrapped(
            f"  ARN: {policy['Arn']}"
        )

        add_wrapped(
            f"  Default Version: "
            f"{policy['DefaultVersionId']}"
        )

        add_line()

    # --------------------------------------------------------
    # COST
    # --------------------------------------------------------

    add_line(
        "COST REPORT - LAST 90 DAYS"
    )

    add_line(
        "-" * 92
    )

    total_cost = 0.0
    ec2_cost = 0.0
    s3_cost = 0.0

    for item in report["costs"]:

        cost = item["Cost"]

        total_cost += cost

        service = item["Service"]

        if "EC2" in service:

            ec2_cost += cost

        elif service == "Amazon Simple Storage Service":

            s3_cost += cost

    other_cost = (
        total_cost
        - ec2_cost
        - s3_cost
    )

    add_line(
        f"EC2 Cost: ${ec2_cost:.2f}"
    )

    add_line(
        f"S3 Cost: ${s3_cost:.2f}"
    )

    add_line(
        f"Other Services: ${other_cost:.2f}"
    )

    add_line(
        f"Total Cost: ${total_cost:.2f}"
    )

    add_line()

    add_line(
        "SERVICE COST BREAKDOWN"
    )

    add_line(
        "-" * 92
    )

    for item in report["costs"]:

        add_wrapped(
            f"{item['Start']} -> "
            f"{item['End']} | "
            f"{item['Service']} | "
            f"${item['Cost']:.2f}"
        )

    add_line()

    add_line(
        "END OF REPORT"
    )

    # Add remaining page
    if current_page:

        pages.append(
            current_page.copy()
        )

    # --------------------------------------------------------
    # PDF OBJECTS
    # --------------------------------------------------------

    objects = []

    # Catalog
    objects.append(
        b"<< /Type /Catalog /Pages 2 0 R >>"
    )

    page_numbers = []

    # Pages object will be created later
    objects.append(
        b"<< /Type /Pages >>"
    )

    # Font
    font_number = 3

    objects.append(
        b"<< /Type /Font "
        b"/Subtype /Type1 "
        b"/BaseFont /Courier >>"
    )

    page_start = len(objects) + 1

    content_numbers = []

    for page in pages:

        # Content stream
        content = []

        content.append(
            "BT"
        )

        content.append(
            "/F3 8 Tf"
        )

        content.append(
            "40 750 Td"
        )

        for line in page:

            content.append(
                f"({escape_pdf(line)}) Tj"
            )

            content.append(
                "0 -15 Td"
            )

        content.append(
            "ET"
        )

        stream = "\n".join(
            content
        ).encode(
            "latin-1",
            errors="replace"
        )

        content_number = len(
            objects
        ) + 1

        objects.append(
            b"<< /Length "
            + str(
                len(stream)
            ).encode()
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        )

        page_number = len(
            objects
        ) + 1

        objects.append(
            (
                f"<< /Type /Page "
                f"/Parent 2 0 R "
                f"/MediaBox [0 0 612 792] "
                f"/Resources << "
                f"/Font << /F3 {font_number} 0 R >> "
                f">> "
                f"/Contents {content_number} 0 R >>"
            ).encode()
        )

        page_numbers.append(
            page_number
        )

    # Update Pages object
    kids = " ".join(
        f"{n} 0 R"
        for n in page_numbers
    )

    objects[1] = (
        f"<< /Type /Pages "
        f"/Kids [{kids}] "
        f"/Count {len(page_numbers)} >>"
    ).encode()

    # --------------------------------------------------------
    # WRITE PDF
    # --------------------------------------------------------

    pdf = bytearray()

    pdf.extend(
        b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    )

    offsets = []

    for number, obj in enumerate(
        objects,
        start=1
    ):

        offsets.append(
            len(pdf)
        )

        pdf.extend(
            f"{number} 0 obj\n".encode()
        )

        pdf.extend(obj)

        pdf.extend(
            b"\nendobj\n"
        )

    xref_position = len(pdf)

    pdf.extend(
        f"xref\n0 {len(objects) + 1}\n".encode()
    )

    pdf.extend(
        b"0000000000 65535 f \n"
    )

    for offset in offsets:

        pdf.extend(
            f"{offset:010d} 00000 n \n".encode()
        )

    pdf.extend(
        (
            f"trailer\n"
            f"<< /Size {len(objects) + 1} "
            f"/Root 1 0 R >>\n"
            f"startxref\n"
            f"{xref_position}\n"
            f"%%EOF\n"
        ).encode()
    )

    with open(
        filename,
        "wb"
    ) as file:

        file.write(pdf)


# ============================================================
# EMAIL PDF
# ============================================================

def send_pdf_email(pdf_path):

    message = MIMEMultipart()

    message["Subject"] = (
        "AWS Cost & Resource Audit Report"
    )

    message["From"] = SENDER_EMAIL

    message["To"] = RECIPIENT_EMAIL

    body = MIMEText(
        """
Hello,

Attached is your AWS Cost & Resource Audit report.

The report contains:
- EC2 inventory
- S3 inventory
- IAM users, roles, groups and policies
- 90-day AWS Cost Explorer data

Regards,
AWS Cost Audit Lambda
""",
        "plain"
    )

    message.attach(body)

    with open(
        pdf_path,
        "rb"
    ) as file:

        attachment = MIMEApplication(
            file.read(),
            _subtype="pdf"
        )

    attachment.add_header(
        "Content-Disposition",
        "attachment",
        filename="AWS-Cost-Audit-Report.pdf"
    )

    message.attach(
        attachment
    )

    response = ses.send_raw_email(
        Source=SENDER_EMAIL,
        Destinations=[
            RECIPIENT_EMAIL
        ],
        RawMessage={
            "Data":
                message.as_bytes()
        }
    )

    return response["MessageId"]


# ============================================================
# SNS NOTIFICATION
# ============================================================

def send_sns_notification(
    status,
    message
):

    sns.publish(

        TopicArn=SNS_TOPIC_ARN,

        Subject=(
            f"AWS Cost Audit - {status}"
        ),

        Message=message
    )


# ============================================================
# LAMBDA HANDLER
# ============================================================

def lambda_handler(
    event,
    context
):

    try:

        print(
            "Starting AWS Cost Audit..."
        )

        # ----------------------------------------------------
        # Account
        # ----------------------------------------------------

        sts = boto3.client(
            "sts",
            region_name=AWS_REGION
        )

        identity = (
            sts.get_caller_identity()
        )

        # ----------------------------------------------------
        # Collect
        # ----------------------------------------------------

        print(
            "Collecting EC2..."
        )

        ec2_data = collect_ec2()

        print(
            "Collecting S3..."
        )

        s3_data = collect_s3()

        print(
            "Collecting IAM users..."
        )

        users = collect_iam_users()

        print(
            "Collecting IAM roles..."
        )

        roles = collect_iam_roles()

        print(
            "Collecting IAM groups..."
        )

        groups = collect_iam_groups()

        print(
            "Collecting IAM policies..."
        )

        policies = collect_iam_policies()

        print(
            "Collecting costs..."
        )

        costs = collect_costs()

        # ----------------------------------------------------
        # Build report
        # ----------------------------------------------------

        report = {

            "account": {

                "AccountId":
                    identity["Account"],

                "Arn":
                    identity["Arn"]
            },

            "ec2":
                ec2_data,

            "s3":
                s3_data,

            "iam": {

                "users":
                    users,

                "roles":
                    roles,

                "groups":
                    groups,

                "policies":
                    policies
            },

            "costs":
                costs
        }

        # ----------------------------------------------------
        # Generate PDF
        # ----------------------------------------------------

        print(
            "Generating PDF..."
        )

        create_pdf(
            report,
            PDF_PATH
        )

        pdf_size = os.path.getsize(
            PDF_PATH
        )

        print(
            f"PDF generated: "
            f"{pdf_size} bytes"
        )

        # ----------------------------------------------------
        # Send SES email
        # ----------------------------------------------------

        print(
            "Sending PDF through SES..."
        )

        ses_message_id = (
            send_pdf_email(
                PDF_PATH
            )
        )

        print(
            "SES Message ID:",
            ses_message_id
        )

        # ----------------------------------------------------
        # SNS notification
        # ----------------------------------------------------

        notification = (
            "AWS Cost Audit completed successfully.\n\n"
            f"Account: {identity['Account']}\n"
            f"EC2 instances: {len(ec2_data)}\n"
            f"S3 buckets: {len(s3_data)}\n"
            f"IAM users: {len(users)}\n"
            f"IAM roles: {len(roles)}\n"
            f"PDF size: {pdf_size} bytes\n\n"
            "The detailed PDF report was sent through SES."
        )

        send_sns_notification(
            "SUCCESS",
            notification
        )

        # ----------------------------------------------------
        # Return
        # ----------------------------------------------------

        return {

            "statusCode":
                200,

            "message":
                "AWS Cost Audit completed successfully.",

            "pdfSize":
                pdf_size,

            "sesMessageId":
                ses_message_id,

            "ec2Instances":
                len(ec2_data),

            "s3Buckets":
                len(s3_data),

            "iamUsers":
                len(users),

            "iamRoles":
                len(roles)
        }

    except Exception as e:

        print(
            "AUDIT FAILED:",
            str(e)
        )

        try:

            send_sns_notification(
                "FAILED",
                (
                    "AWS Cost Audit failed.\n\n"
                    f"Error: {str(e)}"
                )
            )

        except Exception as sns_error:

            print(
                "SNS failure notification "
                "also failed:",
                str(sns_error)
            )

        raise

