# import pulumi
# import pulumi_aws as aws
# import pulumi_synced_folder as synced_folder
# import os
# import mimetypes

# # Import the program's configuration settings.
# config = pulumi.Config()
# path = config.get("path") or "./www"
# index_document = config.get("indexDocument") or "index.html"
# error_document = config.get("errorDocument") or "error.html"

# # Create an S3 bucket.
# # The 'website' configuration is now handled by aws.s3.BucketWebsiteConfigurationV2
# bucket = aws.s3.BucketV2(
#     "s3-website-bucket", # Changed resource name for clarity, you can keep "bucket" if you prefer
#     # acl="public-read" # This is often needed for S3 static website hosting if not using CloudFront OAI
#     # If you are using CloudFront with an Origin Access Identity (OAI) to restrict direct S3 access,
#     # then the bucket itself might not need to be public-read.
#     # However, the original template likely assumes direct S3 access or a simpler CloudFront setup initially.
#     # For now, let's keep it as it was in your original, but be mindful of this.
# )

# # Configure the S3 bucket for website hosting.
# site_bucket_website_configuration = aws.s3.BucketWebsiteConfigurationV2(
#     "s3-website-bucket-website-configuration", # Changed resource name for clarity
#     bucket=bucket.id,  # Use bucket.id to reference the bucket created above
#     index_document=aws.s3.BucketWebsiteConfigurationV2IndexDocumentArgs(
#         suffix=index_document,
#     ),
#     error_document=aws.s3.BucketWebsiteConfigurationV2ErrorDocumentArgs(
#         key=error_document,
#     )
# )

# # Set ownership controls for the new bucket - this is important for S3 static websites
# # when you want to make objects public.
# ownership_controls = aws.s3.BucketOwnershipControls(
#     "ownership-controls",
#     bucket=bucket.id, # Use bucket.id
#     rule=aws.s3.BucketOwnershipControlsRuleArgs(
#         object_ownership="BucketOwnerPreferred", # Or "ObjectWriter" if you manage ACLs per object
#     ),
# )

# # Configure public access block settings.
# # To allow public access for a static website, you generally need to disable blockPublicAcls and blockPublicPolicy.
# # However, if using CloudFront with OAI, you might want to keep these true.
# # For a simple S3 website, you often set these to false.
# public_access_block = aws.s3.BucketPublicAccessBlock(
#     "public-access-block",
#     bucket=bucket.id, # Use bucket.id
#     block_public_acls=False,
#     block_public_policy=False, # Consider this if you need a bucket policy for public access
#     ignore_public_acls=False,
#     restrict_public_buckets=False,
# )

# # Apply a public read policy to the S3 bucket.
# # This is necessary if you want the S3 bucket itself to be directly accessible as a website.
# # If you are ONLY using CloudFront with an Origin Access Identity (OAI), this might not be needed
# # or might be configured differently.
# # For simplicity and to match typical static website hosting directly from S3:
# def public_read_policy_for_bucket(the_bucket_arn): # Renamed parameter for clarity
#     return pulumi.Output.json_dumps({
#         "Version": "2012-10-17",
#         "Statement": [{
#             "Effect": "Allow",
#             "Principal": "*",
#             "Action": ["s3:GetObject"],
#             "Resource": [
#                 f"{the_bucket_arn}/*",
#             ]
#         }]
#     })

# bucket_policy = aws.s3.BucketPolicy("bucket-policy",
#     bucket=bucket.id, # Use bucket.id
#     policy=bucket.arn.apply(public_read_policy_for_bucket),
#     opts=pulumi.ResourceOptions(depends_on=[public_access_block, ownership_controls]) # Ensure this is applied after PAB
# )


# # Use a synced folder to manage the files of the website.
# # Ensure that the ACL for the synced folder is compatible with your bucket's public access settings.
# bucket_folder = synced_folder.S3BucketFolder(
#     "bucket-folder",
#     acl="public-read", # This sets ACLs on individual objects
#     bucket_name=bucket.bucket, # This should be bucket.bucket (the bucket name string)
#     path=path,
#     opts=pulumi.ResourceOptions(depends_on=[bucket_policy]), # Depends on the policy being in place
# )

# # Create a CloudFront CDN to distribute and cache the website.
# # The origin should be the S3 bucket's website endpoint.
# cdn = aws.cloudfront.Distribution(
#     "cdn",
#     enabled=True,
#     origins=[aws.cloudfront.DistributionOriginArgs(
#         origin_id=bucket.arn,
#         domain_name=site_bucket_website_configuration.website_endpoint, # Use the website endpoint from BucketWebsiteConfigurationV2
#         custom_origin_config=aws.cloudfront.DistributionOriginCustomOriginConfigArgs(
#             origin_protocol_policy="http-only", # S3 website endpoints are HTTP
#             http_port=80,
#             https_port=443, # Not used for S3 website endpoint
#             origin_ssl_protocols=["TLSv1.2"],
#         ),
#     )],
#     default_cache_behavior=aws.cloudfront.DistributionDefaultCacheBehaviorArgs(
#         target_origin_id=bucket.arn,
#         viewer_protocol_policy="redirect-to-https",
#         allowed_methods=[
#             "GET",
#             "HEAD",
#             "OPTIONS",
#         ],
#         cached_methods=[
#             "GET",
#             "HEAD",
#             "OPTIONS",
#         ],
#         default_ttl=600,
#         max_ttl=600,
#         min_ttl=600,
#         forwarded_values=aws.cloudfront.DistributionDefaultCacheBehaviorForwardedValuesArgs(
#             query_string=True,
#             cookies=aws.cloudfront.DistributionDefaultCacheBehaviorForwardedValuesCookiesArgs(
#                 forward="none", # Typically 'none' for static sites, unless you use cookies
#             ),
#         ),
#         # It's good practice to specify the S3 origin access identity if you want to restrict direct S3 access
#         # origin_request_policy_id= # Optional: for more control over what's forwarded to origin
#     ),
#     price_class="PriceClass_100",
#     custom_error_responses=[
#         aws.cloudfront.DistributionCustomErrorResponseArgs(
#             error_code=404,
#             response_code=404,
#             response_page_path=f"/{error_document}",
#         ),
#         aws.cloudfront.DistributionCustomErrorResponseArgs( # Often good to have a 403 -> index.html for SPAs
#             error_code=403,
#             response_code=200,
#             response_page_path=f"/{index_document}",
#         ),
#     ],
#     restrictions=aws.cloudfront.DistributionRestrictionsArgs(
#         geo_restriction=aws.cloudfront.DistributionRestrictionsGeoRestrictionArgs(
#             restriction_type="none",
#         ),
#     ),
#     viewer_certificate=aws.cloudfront.DistributionViewerCertificateArgs(
#         cloudfront_default_certificate=True,
#     ),
#     # If you want to use your custom domain with CloudFront, you'll need to configure
#     # aliases and an ACM certificate ARN here.
#     # aliases=["your.custom.domain.com"],
#     # viewer_certificate=aws.cloudfront.DistributionViewerCertificateArgs(
#     #     acm_certificate_arn="arn:aws:acm:us-east-1:123456789012:certificate/your-cert-id",
#     #     ssl_support_method="sni-only",
#     # ),
#     default_root_object=index_document, # Important for CloudFront to serve index.html at the root
#     # It's highly recommended to use an Origin Access Identity (OAI) for CloudFront
#     # to securely access the S3 bucket, rather than making the bucket fully public.
#     # This involves creating an aws.cloudfront.OriginAccessIdentity,
#     # updating the S3 bucket policy to grant access to this OAI,
#     # and then referencing the OAI in the CloudFront origin configuration.
#     # For simplicity, this example keeps the S3 bucket public, but OAI is best practice.
#     # Example for OAI (simplified):
#     # oai = aws.cloudfront.OriginAccessIdentity("oai")
#     # ... then in origins.s3_origin_config:
#     # s3_origin_config=aws.cloudfront.DistributionOriginS3OriginConfigArgs(
#     #     origin_access_identity=oai.cloudfront_access_identity_path,
#     # ),
#     # And update the bucket policy accordingly.
# )

# # Export the URLs and hostnames of the bucket and distribution.
# pulumi.export("s3_bucket_name", bucket.bucket)
# pulumi.export("s3_website_url", site_bucket_website_configuration.website_endpoint)
# pulumi.export("cloudfront_domain_name", cdn.domain_name)
# pulumi.export("website_url", pulumi.Output.concat("https://", cdn.domain_name))

"""
Pulumi Static Website with S3 and CloudFront
Deploys a static website to S3 with CloudFront CDN distribution.

Author: Platform Team
Last Updated: 2025-01-15
"""

import mimetypes
import os

import pulumi
import pulumi_aws as aws

# =============================================================================
# Configuration
# =============================================================================

config = pulumi.Config()
path = config.get("sitePath") or "./www"
index_document = config.get("indexDocument") or "index.html"
error_document = config.get("errorDocument") or "error.html"

# =============================================================================
# S3 Bucket Configuration
# =============================================================================

# Create an S3 bucket for static website hosting
bucket = aws.s3.BucketV2(
    "s3-website-bucket",
    tags={
        "Name": "Static Website Bucket",
        "ManagedBy": "Pulumi",
        "Environment": pulumi.get_stack(),
    },
)

# Configure the S3 bucket for website hosting
site_bucket_website_configuration = aws.s3.BucketWebsiteConfigurationV2(
    "s3-website-bucket-website-configuration",
    bucket=bucket.id,
    index_document=aws.s3.BucketWebsiteConfigurationV2IndexDocumentArgs(
        suffix=index_document,
    ),
    error_document=aws.s3.BucketWebsiteConfigurationV2ErrorDocumentArgs(
        key=error_document,
    ),
)

# Set ownership controls for the bucket
# Required for applying public-read ACLs to objects
ownership_controls = aws.s3.BucketOwnershipControls(
    "ownership-controls",
    bucket=bucket.id,
    rule=aws.s3.BucketOwnershipControlsRuleArgs(
        object_ownership="BucketOwnerPreferred",
    ),
)

# Configure public access block settings
# These must be disabled to allow public website access
public_access_block = aws.s3.BucketPublicAccessBlock(
    "public-access-block",
    bucket=bucket.id,
    block_public_acls=False,
    block_public_policy=False,
    ignore_public_acls=False,
    restrict_public_buckets=False,
)

# =============================================================================
# S3 Bucket Policy
# =============================================================================


def public_read_policy_for_bucket(the_bucket_arn):
    """
    Generate a bucket policy that allows public read access to all objects.

    Args:
        the_bucket_arn: The ARN of the S3 bucket

    Returns:
        JSON string containing the bucket policy
    """
    return pulumi.Output.json_dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "PublicReadGetObject",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": ["s3:GetObject"],
                    "Resource": [f"{the_bucket_arn}/*"],
                }
            ],
        }
    )


bucket_policy = aws.s3.BucketPolicy(
    "bucket-policy",
    bucket=bucket.id,
    policy=bucket.arn.apply(public_read_policy_for_bucket),
    opts=pulumi.ResourceOptions(depends_on=[public_access_block, ownership_controls]),
)

# =============================================================================
# Website Content Upload
# =============================================================================


def upload_files_to_bucket(bucket_name, source_path):
    """
    Upload all files from source directory to S3 bucket root.

    Args:
        bucket_name: Name of the S3 bucket
        source_path: Local directory containing files to upload

    Returns:
        List of BucketObject resources
    """
    bucket_objects = []

    # Walk through the source directory
    for root, dirs, files in os.walk(source_path):
        for file in files:
            # Get full file path
            file_path = os.path.join(root, file)

            # Get relative path from source directory (this is the S3 key)
            relative_path = os.path.relpath(file_path, source_path)

            # Determine content type
            content_type, _ = mimetypes.guess_type(file_path)
            if content_type is None:
                content_type = "application/octet-stream"

            # Create a valid Pulumi resource name (replace invalid characters)
            resource_name = f"file-{relative_path.replace('/', '-').replace('.', '-')}"

            # Upload file to S3 bucket root
            obj = aws.s3.BucketObject(
                resource_name,
                bucket=bucket_name,
                source=pulumi.FileAsset(file_path),
                key=relative_path,  # Files go to bucket root
                content_type=content_type,
                acl="public-read",
                opts=pulumi.ResourceOptions(depends_on=[bucket_policy]),
            )

            bucket_objects.append(obj)

    return bucket_objects


# Upload all files from ./www to bucket root
website_files = upload_files_to_bucket(bucket.bucket, path)

# =============================================================================
# CloudFront Distribution
# =============================================================================

# Create CloudFront distribution for CDN and HTTPS support
cdn = aws.cloudfront.Distribution(
    "cdn",
    enabled=True,
    comment=f"CDN for {pulumi.get_project()} - {pulumi.get_stack()}",
    # Origin configuration - points to S3 website endpoint
    origins=[
        aws.cloudfront.DistributionOriginArgs(
            origin_id=bucket.arn,
            domain_name=site_bucket_website_configuration.website_endpoint,
            custom_origin_config=aws.cloudfront.DistributionOriginCustomOriginConfigArgs(
                origin_protocol_policy="http-only",  # S3 website endpoints use HTTP
                http_port=80,
                https_port=443,
                origin_ssl_protocols=["TLSv1.2"],
            ),
        )
    ],
    # Default cache behavior
    default_cache_behavior=aws.cloudfront.DistributionDefaultCacheBehaviorArgs(
        target_origin_id=bucket.arn,
        viewer_protocol_policy="redirect-to-https",  # Force HTTPS
        allowed_methods=["GET", "HEAD", "OPTIONS"],
        cached_methods=["GET", "HEAD", "OPTIONS"],
        # Cache TTL settings (in seconds)
        default_ttl=600,  # 10 minutes
        max_ttl=600,
        min_ttl=600,
        # Forward query strings but not cookies (typical for static sites)
        forwarded_values=aws.cloudfront.DistributionDefaultCacheBehaviorForwardedValuesArgs(
            query_string=True,
            cookies=aws.cloudfront.DistributionDefaultCacheBehaviorForwardedValuesCookiesArgs(
                forward="none",
            ),
        ),
    ),
    # Use only North America and Europe edge locations (lowest cost tier)
    price_class="PriceClass_100",
    # Custom error responses
    custom_error_responses=[
        # Return custom 404 page
        aws.cloudfront.DistributionCustomErrorResponseArgs(
            error_code=404,
            response_code=404,
            response_page_path=f"/{error_document}",
            error_caching_min_ttl=300,  # Cache 404 responses for 5 minutes
        ),
        # Return index.html for 403 errors (useful for SPAs with client-side routing)
        aws.cloudfront.DistributionCustomErrorResponseArgs(
            error_code=403,
            response_code=200,
            response_page_path=f"/{index_document}",
            error_caching_min_ttl=300,
        ),
    ],
    # Geographic restrictions (none)
    restrictions=aws.cloudfront.DistributionRestrictionsArgs(
        geo_restriction=aws.cloudfront.DistributionRestrictionsGeoRestrictionArgs(
            restriction_type="none",
        ),
    ),
    # Use default CloudFront SSL certificate
    viewer_certificate=aws.cloudfront.DistributionViewerCertificateArgs(
        cloudfront_default_certificate=True,
    ),
    # Default root object - serves this file when accessing the root URL
    default_root_object=index_document,
    # Tags for resource organization
    tags={
        "Name": "Static Website CDN",
        "ManagedBy": "Pulumi",
        "Environment": pulumi.get_stack(),
    },
    # Ensure files are uploaded before creating distribution
    opts=pulumi.ResourceOptions(depends_on=website_files),
)

# =============================================================================
# Outputs
# =============================================================================

# Export important values for reference
pulumi.export("s3_bucket_name", bucket.bucket)
pulumi.export("s3_bucket_arn", bucket.arn)
pulumi.export("s3_website_url", site_bucket_website_configuration.website_endpoint)
pulumi.export("cloudfront_distribution_id", cdn.id)
pulumi.export("cloudfront_domain_name", cdn.domain_name)
pulumi.export("website_url", pulumi.Output.concat("https://", cdn.domain_name))

# Export cache invalidation command for convenience
pulumi.export(
    "cache_invalidation_command",
    pulumi.Output.concat(
        "aws cloudfront create-invalidation --distribution-id ", cdn.id, " --paths '/*'"
    ),
)

# Export file count for verification
pulumi.export("files_uploaded", len(website_files))
