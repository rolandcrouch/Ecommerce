# Django Ecommerce - Portable Docker Setup

## 🚀 Quick Start (Any Machine)

1. **Prerequisites:**
   - Docker 20.10+ 
   - Docker Compose 2.0+

2. **Setup:**
   ```bash
   git clone <your-repo>
   cd ecommerce
   cp env.template .env
   # Edit .env with your configuration
   docker-compose up
   ```

3. **Access:**
   - Application: http://localhost:8000
   - Admin: http://localhost:8000/admin (admin/admin123)
   - Database: localhost:3307 (from host machine)

## 🌍 Tested Platforms

✅ **Linux** (Ubuntu, CentOS, Alpine)  
✅ **macOS** (Intel & Apple Silicon)  
✅ **Windows** (WSL2 + Docker Desktop)  
✅ **Cloud Platforms** (AWS, GCP, Azure)  

## ⚙️ Configuration

### Environment Variables (.env file)

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_PASSWORD` | `defaultpassword` | MySQL password |
| `SECRET_KEY` | `django-insecure-...` | Django secret key |
| `DEBUG` | `False` | Debug mode |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Allowed hosts |
| `WEB_PORT` | `8000` | Web server port |
| `EMAIL_HOST_USER` | `` | Email username (optional) |
| `TWITTER_ENABLED` | `False` | Enable Twitter integration |

### Production Setup

```bash
# Example production .env
SECRET_KEY=your-super-long-random-production-key-here
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
DATABASE_PASSWORD=your-secure-production-password
EMAIL_HOST_USER=noreply@yourdomain.com
EMAIL_HOST_PASSWORD=your-app-password
```

## 🐳 Docker Commands

```bash
# Start services
docker-compose up

# Start in background
docker-compose up -d

# Rebuild and start
docker-compose up --build

# Stop services
docker-compose down

# View logs
docker-compose logs web
docker-compose logs db

# Access Django shell
docker-compose exec web python manage.py shell

# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser
```

## 🔧 Using Pre-built Image

Instead of building locally, use the pre-built image:

1. Edit `docker-compose.yml`:
   ```yaml
   web:
     # build: .  # Comment this out
     image: rolandcrouch/django-ecommerce:latest  # Uncomment this
   ```

2. Run:
   ```bash
   docker-compose pull  # Download latest image
   docker-compose up
   ```

## 🌐 Multi-Platform Support

The image supports multiple architectures:

```bash
# Build for multiple platforms
docker buildx build --platform linux/amd64,linux/arm64 -t your-image:latest --push .

# Run on specific platform
docker run --platform linux/amd64 -p 8000:8000 rolandcrouch/django-ecommerce:latest
```

## 🔒 Security Notes

- **Never commit `.env` files** with real credentials
- Change default passwords in production
- Use strong `SECRET_KEY` in production
- Set `DEBUG=False` in production
- Configure proper `ALLOWED_HOSTS`

## 🚨 Troubleshooting

### Port Already in Use
```bash
# Change ports in .env
WEB_PORT=8001
DATABASE_EXTERNAL_PORT=3308
```

### Database Connection Issues
```bash
# Wait for database to be ready
docker-compose logs db
# Look for: "ready for connections"
```

### Permission Issues
```bash
# Fix file permissions
sudo chown -R $USER:$USER .
```

## 📁 Project Structure

```
ecommerce/
├── Dockerfile              # Container definition
├── docker-compose.yml      # Service orchestration
├── env.template            # Environment template
├── entrypoint.sh           # Container startup script
├── requirements.txt        # Python dependencies
├── manage.py               # Django management
└── ecommerce/
    ├── settings.py         # Django settings
    └── ...
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Test with Docker
4. Submit pull request

## 📞 Support

- **Issues:** Create GitHub issue
- **Documentation:** Check Django docs
- **Docker:** Check Docker docs

---

**This setup ensures your application runs identically on any machine with Docker! 🎉**
