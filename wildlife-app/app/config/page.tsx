"use client"

import * as React from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { toast } from "sonner"
import { Save, RefreshCw } from "lucide-react"
import axios from "axios"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001"

interface ConfigValue {
  key: string
  value: string
  description: string
  type: "string" | "number" | "boolean" | "json"
  category: string
}

const CONFIG_CATEGORIES = [
  {
    name: "Database",
    keys: ["DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT", "DB_NAME"]
  },
  {
    name: "Services",
    keys: ["MOTIONEYE_URL", "SPECIESNET_URL"]
  },
  {
    name: "Notifications",
    keys: [
      "NOTIFICATION_ENABLED",
      "SMTP_HOST",
      "SMTP_PORT",
      "SMTP_USER",
      "SMTP_PASSWORD",
      "NOTIFICATION_EMAIL_FROM",
      "NOTIFICATION_EMAIL_TO",
      "SMS_ENABLED",
      "TWILIO_ACCOUNT_SID",
      "TWILIO_AUTH_TOKEN",
      "TWILIO_PHONE_NUMBER",
      "SMS_PHONE_NUMBERS"
    ]
  },
  {
    name: "Backups",
    keys: [
      "BACKUP_SCHEDULE_DAILY_HOUR",
      "BACKUP_SCHEDULE_WEEKLY_DAY_OF_WEEK",
      "BACKUP_SCHEDULE_WEEKLY_HOUR",
      "BACKUP_RETENTION_COUNT"
    ]
  },
  {
    name: "Archival",
    keys: [
      "ARCHIVAL_ENABLED",
      "ARCHIVAL_ROOT",
      "ARCHIVAL_MIN_CONFIDENCE",
      "ARCHIVAL_MIN_AGE_DAYS"
    ]
  },
  {
    name: "Security",
    keys: [
      "API_KEY_ENABLED",
      "JWT_SECRET_KEY",
      "SESSION_EXPIRY_HOURS"
    ]
  }
]

export default function ConfigPage() {
  const [configs, setConfigs] = React.useState<Record<string, string>>({})
  const [loading, setLoading] = React.useState(true)
  const [saving, setSaving] = React.useState(false)

  React.useEffect(() => {
    loadConfigs()
  }, [])

  const loadConfigs = async () => {
    try {
      setLoading(true)
      // In a real implementation, you'd fetch from an API endpoint
      // For now, we'll use localStorage or show a message
      const response = await axios.get(`${API_URL}/api/config`)
      setConfigs(response.data)
    } catch (error: any) {
      // If endpoint doesn't exist, show a message
      if (error.response?.status === 404) {
        toast.info("Configuration API endpoint not yet implemented. This is a UI preview.")
        // Set some default values for preview
        setConfigs({
          DB_HOST: "localhost",
          DB_PORT: "5432",
          DB_NAME: "wildlife",
          MOTIONEYE_URL: "http://localhost:8765",
          SPECIESNET_URL: "http://localhost:8000",
          NOTIFICATION_ENABLED: "false",
          SMS_ENABLED: "false"
        })
      } else {
        toast.error("Failed to load configuration")
      }
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    try {
      setSaving(true)
      const response = await axios.post(`${API_URL}/api/config`, configs)
      toast.info(response.data.message || "Configuration is read-only. Edit .env file to change settings.")
    } catch (error: any) {
      if (error.response?.data?.message) {
        toast.info(error.response.data.message)
      } else {
        toast.error("Configuration is read-only. Edit .env file to change settings.")
      }
    } finally {
      setSaving(false)
    }
  }

  const updateConfig = (key: string, value: string) => {
    setConfigs(prev => ({ ...prev, [key]: value }))
  }

  if (loading) {
    return (
      <div className="container mx-auto p-6">
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </div>
    )
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">System Settings</h1>
          <p className="text-muted-foreground mt-2">
            View current system configuration (read-only)
          </p>
        </div>
        <div className="flex gap-2">
          <Button onClick={loadConfigs} variant="outline" size="sm">
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
        </div>
      </div>

      <div className="bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <div className="text-blue-600 dark:text-blue-400 mt-0.5">
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
            </svg>
          </div>
          <div className="flex-1">
            <h3 className="font-semibold text-blue-900 dark:text-blue-100 mb-1">Read-Only Configuration</h3>
            <p className="text-sm text-blue-800 dark:text-blue-200">
              Configuration values are loaded from the <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">.env</code> file. 
              To change settings, edit <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">wildlife-app/backend/.env</code> and restart the backend server.
            </p>
          </div>
        </div>
      </div>

      <div className="grid gap-6">
        {CONFIG_CATEGORIES.map((category) => (
          <Card key={category.name}>
            <CardHeader>
              <CardTitle>{category.name}</CardTitle>
              <CardDescription>
                Configure {category.name.toLowerCase()} settings
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {category.keys.map((key) => {
                const isPassword = key.toLowerCase().includes("password") || key.toLowerCase().includes("secret") || key.toLowerCase().includes("token")
                const isBoolean = key.includes("ENABLED")
                const value = configs[key] || ""

                if (isBoolean) {
                  return (
                    <div key={key} className="flex items-center justify-between">
                      <Label htmlFor={key}>{key}</Label>
                      <Switch
                        id={key}
                        checked={value === "true"}
                        onCheckedChange={(checked) => updateConfig(key, checked ? "true" : "false")}
                        disabled
                      />
                    </div>
                  )
                }

                return (
                  <div key={key} className="space-y-2">
                    <Label htmlFor={key}>{key}</Label>
                    {isPassword ? (
                      <Input
                        id={key}
                        type="password"
                        value={value}
                        onChange={(e) => updateConfig(key, e.target.value)}
                        placeholder={`Enter ${key}`}
                        disabled
                        className="bg-muted"
                      />
                    ) : (
                      <Input
                        id={key}
                        type="text"
                        value={value}
                        onChange={(e) => updateConfig(key, e.target.value)}
                        placeholder={`Enter ${key}`}
                        disabled
                        className="bg-muted"
                      />
                    )}
                  </div>
                )
              })}
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>How to Change Settings</CardTitle>
          <CardDescription>
            Configuration is managed through environment variables
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <h4 className="font-semibold mb-2">Steps to Update Configuration:</h4>
            <ol className="list-decimal list-inside space-y-1 text-sm text-muted-foreground">
              <li>Edit the <code className="bg-muted px-1 rounded">wildlife-app/backend/.env</code> file</li>
              <li>Modify the environment variables you want to change</li>
              <li>Restart the backend server for changes to take effect</li>
            </ol>
          </div>
          <div className="pt-2 border-t">
            <p className="text-sm text-muted-foreground">
              See <code className="bg-muted px-1 rounded">wildlife-app/backend/ENV_SETUP.md</code> for a complete list of available configuration options.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

