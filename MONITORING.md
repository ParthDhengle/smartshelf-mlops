# SmartShelf Monitoring Stack

Complete monitoring setup with Prometheus and Grafana for MLOps and business metrics.

## 🚀 Quick Start

### 1. Start Monitoring Stack

```bash
# Start Prometheus + Grafana
docker-compose -f docker-compose.monitoring.yml up -d

# Check services are running
docker ps
```

### 2. Access Dashboards

- **Grafana**: http://localhost:3001
  - Username: `admin`
  - Password: `smartshelf`
  - Dashboard: "SmartShelf MLOps Dashboard"

- **Prometheus**: http://localhost:9090

### 3. Start SmartShelf API

```bash
# Make sure your API is running on port 8000
python -m smartshelf.api.main
```

## 📊 Monitored Metrics

### API Performance
- Request rate by endpoint and status code
- Request latency (p50, p95, p99)
- Health status (DB, MLflow connectivity)

### ML Model Performance
- **Prediction Metrics**: Count, latency by model
- **Model Quality**: RMSE, MAE, R² scores
- **Drift Detection**: Feature drift, prediction drift
- **Training**: Duration, last training timestamp

### Business Metrics
- **Inventory Health**: Stockout rate, reorder alerts
- **Model Impact**: Total predictions served

## 🔧 Configuration

### Prometheus Scraping

The API exposes metrics at: `http://localhost:8000/metrics`

Prometheus scrapes this endpoint every 15 seconds.

### Grafana Provisioning

Dashboards and data sources are automatically provisioned:
- **Data Source**: Prometheus (automatic)
- **Dashboard**: SmartShelf MLOps (automatic)

### Background Jobs

The API automatically:
- Updates inventory health metrics every 5 minutes
- Records prediction latency and counts on each ML endpoint call
- Updates model performance metrics during training
- Sends drift detection results to Prometheus

## 🛠 Manual Operations

### Trigger Drift Detection

```bash
# Via API endpoint
curl http://localhost:8000/api/v1/admin/drift-check
```

### Refresh Model Cache

```bash
# Force reload models from MLflow
curl -X POST http://localhost:8000/api/v1/admin/refresh-models
```

### View Raw Metrics

```bash
# See all current metrics
curl http://localhost:8000/metrics
```

## 📈 Dashboard Panels

### Row 1: API Performance
- Request rate by endpoint
- Latency percentiles (p50/p95/p99)

### Row 2: Model Performance  
- RMSE and MAE over time by model
- Model training metrics

### Row 3: Drift Monitoring
- Overall drift score gauge
- Feature drift count
- Prediction drift p-value

### Row 4: Business Impact
- Prediction latency by model
- Stockout rate gauge
- Reorder alerts count

## 🚨 Alerts & Thresholds

### Drift Detection
- **Green**: Drift score < 0.15
- **Yellow**: 0.15 ≤ drift score < 0.3  
- **Red**: Drift score ≥ 0.3 (triggers retraining)

### Stockout Monitoring
- **Green**: <5% stockout rate
- **Yellow**: 5-15% stockout rate
- **Red**: >15% stockout rate

### Prediction Drift  
- **Red**: p-value < 0.01
- **Yellow**: 0.01 ≤ p-value < 0.05
- **Green**: p-value ≥ 0.05

## 🔄 Data Retention

- **Prometheus**: 30 days of metrics history
- **Grafana**: Persistent dashboards and settings
- **API**: Real-time metrics collection

## 🐛 Troubleshooting

### No Data in Grafana
1. Check API is running on port 8000: `curl http://localhost:8000/health`
2. Check Prometheus is scraping: http://localhost:9090/targets
3. Verify metrics endpoint: `curl http://localhost:8000/metrics`

### Missing ML Metrics
1. Make ML predictions to generate data: `curl -X POST http://localhost:8000/api/v1/predict-demand -d '{"product_id":1,"store_id":1,"start_date":"2024-01-01","end_date":"2024-01-07"}' -H "Content-Type: application/json"`
2. Run drift detection: `curl http://localhost:8000/api/v1/admin/drift-check`
3. Check training pipeline for model performance metrics

### Docker Issues
```bash
# Restart monitoring stack
docker-compose -f docker-compose.monitoring.yml down
docker-compose -f docker-compose.monitoring.yml up -d

# Check logs
docker logs smartshelf-prometheus
docker logs smartshelf-grafana
```