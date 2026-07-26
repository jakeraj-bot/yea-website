from django.db import models


class ContactMessage(models.Model):
    name = models.CharField(max_length=120)
    email = models.EmailField()
    topic = models.CharField(max_length=64)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} — {self.get_topic_display()} ({self.created_at:%Y-%m-%d})"

    def get_topic_display(self):
        labels = {
            "after_school": "After-school program",
            "summer_camp": "Summer camp",
            "partnership": "Partnership",
            "donation": "Donation",
            "general": "General",
        }
        return labels.get(self.topic, self.topic)
