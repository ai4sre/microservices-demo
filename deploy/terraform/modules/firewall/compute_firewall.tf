resource "google_compute_firewall" "allow-internal" {
  allow {
    protocol = "all"
  }
  direction = "INGRESS"
  disabled = "false"
  name = "allow-internal"
  network = "default"
  priority = "10"
  project = var.project
  source_ranges = []
}

resource "google_compute_firewall" "deny-ssh" {
  deny {
    protocol = "tcp"
    ports = ["22"]
  }
  direction = "INGRESS"
  disabled = "false"
  name = "deny-ssh"
  network = "default"
  priority = "1000"
  project = var.project
  source_ranges = ["0.0.0.0/0"]
}

resource "google_compute_firewall" "deny-rdp" {
  deny {
    protocol = "tcp"
    ports = ["3389"]
  }
  direction = "INGRESS"
  disabled = "false"
  name = "deny-rdp"
  network = "default"
  priority = "1000"
  project = var.project
  source_ranges = ["10.128.0.0/9"]
}
