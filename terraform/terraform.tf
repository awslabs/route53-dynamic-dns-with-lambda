/**
 * Variables
 */

variable "route53_zone_name" {
}
variable "s3_bucket_name" {
}
variable "aws_region" {
  default = "us-east-1"
}
variable "aws_profile" {
  default = "default"
}
variable "aws_access_key" {
}
variable "aws_secret_key" {
}


provider "aws" {
  access_key = "${var.aws_access_key}"
  secret_key = "${var.aws_secret_key}"
  region = "${var.aws_region}"
  profile = "${var.aws_profile}"
}

/**
 * Route53 Zone Configuration
 */
resource "aws_route53_zone" "ddns_route53_zone" {
  name = "${var.route53_zone_name}"

  tags {
    Name = "DynamicDNS"
  }
}

/**
 * S3 Configuration
 */
data "template_file" "ddns_config_file" {
  template = "${file("config.json")}"

  vars {
    zone_id = "${aws_route53_zone.ddns_route53_zone.zone_id}"
	aws_region = "${var.aws_region}"
  }
}

resource "aws_s3_bucket" "ddns_config_bucket" {
  bucket = "${var.s3_bucket_name}"
  acl = "private"

  tags {
    Name = "DynamicDNS"
  }
}

resource "aws_s3_bucket_object" "object" {
  bucket = "${aws_s3_bucket.ddns_config_bucket.bucket}"
  key = "config.json"
  content = "${data.template_file.ddns_config_file.rendered}"
}


/**
 * IAM Configuration
 *
 * Generate an IAM role and policy for the lambda handler with permissions
 * to read the config file (from S3) and read / write to Route53 zone
 */

data "aws_iam_policy_document" "ddns_lambda_assume_policy" {
  statement {
    effect = "Allow"
    actions = [ "sts:AssumeRole" ]

    principals {
      type = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ddns_role_lambda" {
  name = "dynamic_dns_lambda_execution_role"
  assume_role_policy = "${data.aws_iam_policy_document.ddns_lambda_assume_policy.json}"
}

data "aws_iam_policy_document" "ddns_policy_document" {
  statement {
    effect = "Allow"
    actions = [
      "route53:ChangeResourceRecordSets",
      "route53:ListResourceRecordSets"
    ]
    resources = [
      "arn:aws:route53:::hostedzone/${aws_route53_zone.ddns_route53_zone.zone_id}"
    ]
  }
  
  statement {
    effect = "Allow"
    actions = [
      "route53:GetChange"
    ]
    resources = [
      "arn:aws:route53:::change/*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
    resources = [
      "arn:aws:logs:*:*:*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "s3:Get*",
      "s3:List*"
    ]
    resources = [
      "${aws_s3_bucket.ddns_config_bucket.arn}/*"
      /*"arn:aws:s3:::${var.s3_bucket_name}/*"*/
    ]
  }
  
  depends_on = [
    "aws_route53_zone.ddns_route53_zone",
	"aws_s3_bucket.ddns_config_bucket"
  ]
}

resource "aws_iam_policy" "ddns_policy" {
  name = "dynamic_dns_lambda_execution_policy"
  policy = "${data.aws_iam_policy_document.ddns_policy_document.json}"
}

resource "aws_iam_role_policy_attachment" "ddns_attachment" {
  role = "${aws_iam_role.ddns_role_lambda.name}"
  policy_arn = "${aws_iam_policy.ddns_policy.arn}"
}


/**
 * Lambda Configuration
 * 
 * Upload the python script and grant API Gateway permission to invoke the script
 */
resource "aws_lambda_function" "ddns_lambda_function" {
  filename = "dynamic_dns_lambda.zip"
  function_name = "dynamic_dns_lambda"
  role = "${aws_iam_role.ddns_role_lambda.arn}"
  handler = "dynamic_dns_lambda.lambda_handler"
  runtime = "python2.7"
  timeout = "3"
  source_code_hash = "${base64sha256(file("dynamic_dns_lambda.zip"))}"
}

resource "aws_lambda_permission" "ddns_api_permission" {
  statement_id = "AllowExecutionFromAPIGateway"
  action = "lambda:InvokeFunction"
  function_name = "${aws_lambda_function.ddns_lambda_function.function_name}"
  principal = "apigateway.amazonaws.com"
}

/**
 * Api Gateway Configuration
 */


resource "aws_api_gateway_rest_api" "ddns_api" {
  name = "dynamic_dns_lambda_api"
  depends_on = ["aws_lambda_function.ddns_lambda_function"]
}

/*resource "aws_api_gateway_resource" "ddns_api_resource" {
  rest_api_id = "${aws_api_gateway_rest_api.ddns_api.id}"
  parent_id = "${aws_api_gateway_rest_api.ddns_api.root_resource_id}"
  path_part = "ddns"
}*/

resource "aws_api_gateway_method" "ddns_api_resource_get" {
  rest_api_id = "${aws_api_gateway_rest_api.ddns_api.id}"
  resource_id = "${aws_api_gateway_rest_api.ddns_api.root_resource_id}"
  http_method = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_method_response" "200" {
  rest_api_id = "${aws_api_gateway_rest_api.ddns_api.id}"
  resource_id = "${aws_api_gateway_rest_api.ddns_api.root_resource_id}"
  http_method = "${aws_api_gateway_method.ddns_api_resource_get.http_method}"
  status_code = "200"
  response_models = {
      "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration" "ddns_api_resource_get_integration" {
  rest_api_id = "${aws_api_gateway_rest_api.ddns_api.id}"
  resource_id = "${aws_api_gateway_rest_api.ddns_api.root_resource_id}"
  http_method = "${aws_api_gateway_method.ddns_api_resource_get.http_method}"
  integration_http_method = "POST"
  type = "AWS"
  uri = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/${aws_lambda_function.ddns_lambda_function.arn}/invocations"
}

resource "aws_api_gateway_integration_response" "ddns_api_integration_response" {
  rest_api_id = "${aws_api_gateway_rest_api.ddns_api.id}"
  resource_id = "${aws_api_gateway_rest_api.ddns_api.root_resource_id}"
  http_method = "${aws_api_gateway_method.ddns_api_resource_get.http_method}"
  status_code = "${aws_api_gateway_method_response.200.status_code}"
  selection_pattern = ""
  depends_on = ["aws_api_gateway_integration.ddns_api_resource_get_integration"]
  response_templates = {
      "application/json" = "${file("api_mapping_template")}"
  }
}

resource "aws_api_gateway_deployment" "ddns_deployment" {
  rest_api_id = "${aws_api_gateway_rest_api.ddns_api.id}"
  depends_on = ["aws_api_gateway_integration_response.ddns_api_integration_response"]
  stage_name = "prod"
}
