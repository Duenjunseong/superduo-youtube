# Generated by Django 5.2.1 on 2025-05-24 04:36

import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="File",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("filename", models.CharField(max_length=255)),
                ("file_path", models.CharField(max_length=1000)),
                ("file_size", models.BigIntegerField(default=0)),
                ("file_type", models.CharField(blank=True, max_length=20, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="Job",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("url", models.URLField(max_length=2000)),
                ("src_url", models.URLField(blank=True, max_length=2000, null=True)),
                ("title", models.CharField(blank=True, max_length=500, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "대기 중"),
                            ("running", "진행 중"),
                            ("done", "완료"),
                            ("cancelled", "취소"),
                            ("pending", "대기 중"),
                            ("processing", "처리 중"),
                            ("completed", "완료"),
                            ("failed", "실패"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                (
                    "quality",
                    models.CharField(
                        choices=[
                            ("highest", "최상 품질"),
                            ("720p", "720p"),
                            ("480p", "480p"),
                            ("360p", "360p"),
                            ("audio", "오디오만"),
                        ],
                        default="highest",
                        max_length=20,
                    ),
                ),
                ("task_id", models.CharField(blank=True, max_length=100, null=True)),
                ("error_message", models.TextField(blank=True, null=True)),
                ("error_msg", models.TextField(blank=True, null=True)),
                ("memo", models.TextField(blank=True, null=True)),
                ("progress", models.FloatField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="Tag",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=50)),
                ("color", models.CharField(default="pastel-blue", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
    ]
