"""
Pulumi Static Website with S3 and CloudFront
"""

import pulumi
import pulumi_aws as aws
import pulumi_synced_folder as synced_folder

# Config
config = pulumi.Config()
path = config.get("path") or "./www"
index_document = config.get("indexDocument") or "index.html"
error_document = config.get("errorDocument") or "error.html"

# 1. S3 bucket (non-deprecated)
bucket = aws.s3.Bucket("s3-website-bucket")

# 2. Website configuration (non-V2)
site_bucket_website_configuration = aws.s3.BucketWebsiteConfiguration(
    "s3-website-bucket-website-configuration",
    bucket=bucket.id,
    index_document=aws.s3.BucketWebsiteConfigurationIndexDocumentArgs(
        suffix=index_document,  # e.g. "index.html" (no slashes)
    ),
    error_document=aws.s3.BucketWebsiteConfigurationErrorDocumentArgs(
        key=error_document,  # e.g. "error.html" (no slashes)
    ),
)

# 3. Ownership controls
ownership_controls = aws.s3.BucketOwnershipControls(
    "ownership-controls",
    bucket=bucket.id,
    rule=aws.s3.BucketOwnershipControlsRuleArgs(
        object_ownership="BucketOwnerPreferred",
    ),
)

# 4. Public access block (allow public website policy)
public_access_block = aws.s3.BucketPublicAccessBlock(
    "public-access-block",
    bucket=bucket.id,
    block_public_acls=False,
    block_public_policy=False,
    ignore_public_acls=False,
    restrict_public_buckets=False,
)


# 5. Bucket policy for public read
def public_read_policy_for_bucket(the_bucket_arn):
    return pulumi.Output.json_dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": ["s3:GetObject"],
                    "Resource": [f"{the_bucket_arn}/*"],
                },
            ],
        },
    )


bucket_policy = aws.s3.BucketPolicy(
    "bucket-policy",
    bucket=bucket.id,
    policy=bucket.arn.apply(public_read_policy_for_bucket),
    opts=pulumi.ResourceOptions(depends_on=[public_access_block, ownership_controls]),
)

# 6. Pulumi-managed sync of ./www -> S3 (no aws CLI)
bucket_folder = synced_folder.S3BucketFolder(
    "bucket-folder",
    acl="public-read",
    bucket_name=bucket.bucket,
    path=path,
    # managed_objects defaults to True, but we set it explicitly for clarity.
    managed_objects=True,
    opts=pulumi.ResourceOptions(depends_on=[bucket_policy]),
)

# 7. CloudFront Distribution using the S3 website endpoint as origin
cdn = aws.cloudfront.Distribution(
    "cdn",
    enabled=True,
    origins=[
        aws.cloudfront.DistributionOriginArgs(
            origin_id=bucket.arn,
            domain_name=site_bucket_website_configuration.website_endpoint,
            custom_origin_config=aws.cloudfront.DistributionOriginCustomOriginConfigArgs(
                origin_protocol_policy="http-only",
                http_port=80,
                https_port=443,
                origin_ssl_protocols=["TLSv1.2"],
            ),
        ),
    ],
    default_cache_behavior=aws.cloudfront.DistributionDefaultCacheBehaviorArgs(
        target_origin_id=bucket.arn,
        viewer_protocol_policy="redirect-to-https",
        allowed_methods=["GET", "HEAD", "OPTIONS"],
        cached_methods=["GET", "HEAD", "OPTIONS"],
        default_ttl=600,
        max_ttl=600,
        min_ttl=600,
        forwarded_values=aws.cloudfront.DistributionDefaultCacheBehaviorForwardedValuesArgs(
            query_string=True,
            cookies=aws.cloudfront.DistributionDefaultCacheBehaviorForwardedValuesCookiesArgs(
                forward="none",
            ),
        ),
    ),
    price_class="PriceClass_100",
    custom_error_responses=[
        aws.cloudfront.DistributionCustomErrorResponseArgs(
            error_code=404,
            response_code=404,
            response_page_path=f"/{error_document}",
        ),
        aws.cloudfront.DistributionCustomErrorResponseArgs(
            error_code=403,
            response_code=200,
            response_page_path=f"/{index_document}",
        ),
    ],
    restrictions=aws.cloudfront.DistributionRestrictionsArgs(
        geo_restriction=aws.cloudfront.DistributionRestrictionsGeoRestrictionArgs(
            restriction_type="none",
        ),
    ),
    viewer_certificate=aws.cloudfront.DistributionViewerCertificateArgs(
        cloudfront_default_certificate=True,
    ),
    default_root_object=index_document,
)

# 8. Outputs
pulumi.export("s3_bucket_name", bucket.bucket)
pulumi.export("s3_bucket_arn", bucket.arn)
pulumi.export("s3_website_url", site_bucket_website_configuration.website_endpoint)
pulumi.export("cloudfront_domain_name", cdn.domain_name)
pulumi.export("cloudfront_distribution_id", cdn.id)
pulumi.export("website_url", pulumi.Output.concat("https://", cdn.domain_name))
pulumi.export(
    "cache_invalidation_command",
    pulumi.Output.concat(
        "aws cloudfront create-invalidation --distribution-id ",
        cdn.id,
        " --paths '/*'",
    ),
)
