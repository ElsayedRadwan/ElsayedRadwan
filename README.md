# GCP Native Backup & Disaster Recovery Portal

A professional, enterprise-grade backup and disaster recovery management platform built specifically for Google Cloud Platform. Streamline your data protection strategy with seamless integration to GCP Backup & Disaster Recovery services.

## 🎯 Core Features

### 💾 Quick Restore
- Single-click VM recovery from backups
- Configurable target zone and network
- Real-time operation tracking
- Instant failover capability

### 📋 Recovery Plans
- Multi-VM coordinated recovery
- Application-stack aware restoration
- Automated task orchestration
- Bulk recovery operations

### 📅 Backup Management
- GCP Backup & Disaster Recovery integration
- Automated backup scheduling
- Retention policy management
- Backup plan creation and monitoring

### 📊 Compliance & Monitoring
- Audit logging and compliance reports
- Job history with detailed tracking
- Operation status monitoring
- Recovery time objective (RTO) tracking

### 🔐 Enterprise Security
- OAuth 2.0 authentication
- CSRF protection
- Input validation & sanitization
- Firestore-backed audit trail

## 🏗️ Architecture

- **Backend**: Python Flask with modular blueprints
- **Frontend**: Bootstrap 5 responsive UI with dark/light mode
- **Database**: Google Cloud Firestore + Cloud Datastore
- **Deployment**: Google Cloud Run (serverless)
- **Authentication**: Google OAuth 2.0
- **Integration**: Native GCP Backup & Disaster Recovery APIs

## 📦 Tech Stack

- **Python 3.9+** with Flask 3.0
- **Google Cloud SDKs** (Firestore, Datastore, Backup & Disaster Recovery)
- **Bootstrap 5.3** for responsive UI
- **Flask-WTF** for CSRF protection

## 🚀 Deployment

### Quick Start

```bash
# Build Docker image
docker build -t restore-app:latest .

# Deploy to Cloud Run
gcloud run deploy restore-app \
  --image restore-app:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

### Environment Variables

- `GOOGLE_CLOUD_PROJECT`: GCP Project ID (default: gcp-internal-lab)
- `FLASK_SECRET`: Flask session secret key
- `PORT`: HTTP port (default: 8080)

## 📝 Usage

1. **Login** with your Google account
2. **Quick Restore**: Select a backup and restore a VM
3. **Create Plans**: Set up multi-VM recovery orchestration
4. **Monitor**: Track jobs and compliance status

## ⚙️ Security Features

- ✅ Input validation on all user inputs
- ✅ CSRF token protection on all forms
- ✅ Specific exception handling (no bare except clauses)
- ✅ Secure database initialization with proper None checks
- ✅ Thread-safe operations

## 📄 License

Internal Use - GCP Backup & DR Solutions
│   ├── storage_manager/   # Cloud Storage operations
│   ├── iam_jit/          # Identity & Access (planned)
│   └── cost_optimizer/   # Cost analysis (planned)
├── templates/            # Jinja2 templates
├── static/               # CSS, JS, images
├── requirements.txt      # Python dependencies
├── Dockerfile           # Container configuration
└── .gitignore          # Git ignore rules
```

## Setup & Deployment

### Local Development

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set environment variables:
   ```bash
   export GOOGLE_CLOUD_PROJECT=your-project-id
   export FLASK_SECRET=your-secret-key
   ```

5. Run the application:
   ```bash
   flask run
   ```

### Cloud Deployment

The application is designed to run on Google Cloud Run:

1. Build and push Docker image:
   ```bash
   gcloud builds submit --tag gcr.io/$PROJECT_ID/restore-app
   ```

2. Deploy to Cloud Run:
   ```bash
   gcloud run deploy restore-app \
     --image gcr.io/$PROJECT_ID/restore-app \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated
   ```

## Configuration

### OAuth Setup
1. Create OAuth 2.0 credentials in Google Cloud Console
2. Add authorized redirect URIs for your domain
3. Update `CLIENT_ID` in `app.py`

### Firestore Database
1. Create a Firestore database in Native mode
2. Update database ID in the Firestore client initialization

### GCP Permissions
Ensure the service account has the following roles:
- `roles/backupdr.admin`
- `roles/compute.admin`
- `roles/storage.admin`
- `roles/datastore.user`

## API Endpoints

### Backup & DR
- `GET /backup-plans` - List backup plans
- `POST /backup-plans/new` - Create backup plan
- `GET /api/backup-jobs/live` - SSE for live job updates
- `POST /api/cost-estimate` - Cost estimation

### Compute
- `GET /compute` - Compute dashboard
- `POST /api/compute/create-vm` - Create VM
- `POST /api/compute/bulk-create` - Bulk VM creation

### Storage
- `GET /storage` - Storage dashboard
- `POST /api/storage/create-bucket` - Create bucket

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue in this repository
- Contact the development team

---

**Built with ❤️ for Google Cloud Platform**