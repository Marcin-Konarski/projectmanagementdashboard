output "alb_dns_name" {
  description = "ALB DNS name to access the backend API"
  value       = aws_lb.main.dns_name
}
