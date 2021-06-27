terraform {
  required_providers {
    google = {
      source = "hashicorp/google"
    }
    google = {
      source = "hashicorp/google-beta"
    }
  }
  required_version = ">= 1.0"
}

provider "google" {
  credentials = file(var.credential)
  project     = var.project
  region      = var.region
}

provider "google-beta" {
  credentials = file(var.credential)
  project = var.project
  region  = var.region
}

module "firewall" {
  source  = "./modules/firewall"
  project = var.project
}
