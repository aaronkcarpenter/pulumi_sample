"""

Pulumi Static Website with S3 and CloudFront
Deploys a static website to S3 with CloudFront CDN distribution.

"""

import pulumi
import pulumi_aws as aws
import pulumi_synced_folder as synced_folder

# Import the program's configuration settings.
config = pulumi.Config()
path = config.get("path") or "./www"
index_document = config.get("indexDocument") or "index.html"
error_document = config.get("errorDocument") or "error.html"

# Create an S3 bucket.
bucket = aws.s3.BucketV2("s3-website-bucket")

# Configure the S3 bucket for website hosting.
# AWS requires JUST the filename, no paths allowed
site_bucket_website_configuration = aws.s3.BucketWebsiteConfigurationV2(
    "s3-website-bucket-website-configuration",
    bucket=bucket.id,
    index_document=aws.s3.BucketWebsiteConfigurationV2IndexDocumentArgs(
        suffix=index_document,  # Must be just "index.html"
    ),
    error_document=aws.s3.BucketWebsiteConfigurationV2ErrorDocumentArgs(
        key=error_document,  # Must be just "error.html"
    ),
)

# Set ownership controls for the new bucket
ownership_controls = aws.s3.BucketOwnershipControls(
    "ownership-controls",
    bucket=bucket.id,
    rule=aws.s3.BucketOwnershipControlsRuleArgs(
        object_ownership="BucketOwnerPreferred",
    ),
)

# Configure public access block settings.
public_access_block = aws.s3.BucketPublicAccessBlock(
    "public-access-block",
    bucket=bucket.id,
    block_public_acls=False,
    block_public_policy=False,
    ignore_public_acls=False,
    restrict_public_buckets=False,
)


# Apply a public read policy to the S3 bucket.
def public_read_policy_for_bucket(the_bucket_arn):
    return pulumi.Output.json_dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": ["s3:GetObject"],
                    "Resource": [
                        f"{the_bucket_arn}/*",
                    ],
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


bucket_folder = synced_folder.S3BucketFolder(
    "bucket-folder",
    acl="public-read",
    bucket_name=bucket.bucket,
    path=path,
    managed_objects=False,
    opts=pulumi.ResourceOptions(depends_on=[bucket_policy]),
)

# Create a CloudFront CDN to distribute and cache the website.
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
            response_page_path=f"/{error_document}",  # "/error.html"
        ),
        aws.cloudfront.DistributionCustomErrorResponseArgs(
            error_code=403,
            response_code=200,
            response_page_path=f"/{index_document}",  # "/index.html"
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
    default_root_object=index_document,  # "index.html"
)

# Export the URLs and hostnames of the bucket and distribution.
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
