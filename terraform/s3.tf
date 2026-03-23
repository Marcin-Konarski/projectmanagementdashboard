resource "aws_s3_bucket" "documents" {
  bucket = var.s3_bucket_name

  tags = { Name = "${var.project_name}-documents" }
}

resource "aws_s3_bucket_public_access_block" "documents" {
  bucket = aws_s3_bucket.documents.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
