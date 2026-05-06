# GCP One Portal for All Operations

A comprehensive web portal for managing Google Cloud Platform operations including Backup & Disaster Recovery, Compute Engine, Cloud Storage, IAM/JIT Access, and Cost Optimization.

## Features

### 🔄 Backup & Disaster Recovery
- Create and manage backup plans for GCP VMs
- Real-time monitoring of backup jobs
- Compliance reporting and vault management
- Automated retention policies
- Cost estimation for backup storage

### 🖥️ Compute Factory
- Bulk VM creation from Excel uploads
- VM lifecycle management
- Automated provisioning workflows

### 🗄️ Cloud Storage Manager
- Bucket creation and configuration
- Storage lifecycle policies
- Access control management
- Cost monitoring and optimization

### 🔐 IAM & JIT Access
- Just-In-Time access management
- Role-based access control
- Audit logging and compliance

### 💰 Cost Optimization
- Resource usage analysis
- Cost forecasting and budgeting
- Optimization recommendations

## Architecture

- **Backend**: Python Flask with modular blueprints
- **Frontend**: HTML/CSS/JavaScript with Jinja2 templates
- **Database**: Google Cloud Firestore
- **Deployment**: Google Cloud Run with Docker
- **Authentication**: Google OAuth 2.0

## Project Structure

```
restore-app/
├── app.py                 # Main Flask application
├── modules/               # Feature modules
│   ├── backup_plans.py    # Backup & DR functionality
│   ├── compute_factory/   # VM management
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