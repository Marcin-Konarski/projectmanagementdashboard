output "alb_dns_name" {
  description = "ALB DNS name to access the backend API"
  value       = aws_lb.main.dns_name
}

output "backend_https_url" {
  description = "Configured public HTTPS URL for backend API"
  value       = var.backend_base_url
}

output "lambda_api_key" {
  description = "API key for Lambda authentication (set as LAMBDA_API_KEY env var in backend)"
  value       = random_password.lambda_api_key.result
  sensitive   = true
}
