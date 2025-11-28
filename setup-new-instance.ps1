# Setup script to install required packages on the new instance
$INSTANCE_ID = "i-039f228cef7663944"
$REGION = "us-east-2"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Installing Required Packages on Instance" -ForegroundColor Cyan
Write-Host "Instance: $INSTANCE_ID" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Install AWS CLI and other required packages
Write-Host "Sending setup commands to instance..." -ForegroundColor Yellow

$commandId = aws ssm send-command `
  --region $REGION `
  --instance-ids $INSTANCE_ID `
  --document-name "AWS-RunShellScript" `
  --comment "Install required packages for deployment" `
  --parameters commands="sudo apt-get update -y","sudo apt-get install -y awscli python3-pip python3-venv unzip","mkdir -p /home/ubuntu/eduquest-backend","sudo chown ubuntu:ubuntu /home/ubuntu/eduquest-backend","echo Setup_complete" `
  --timeout-seconds 600 `
  --output text `
  --query 'Command.CommandId'

Write-Host "Command ID: $commandId" -ForegroundColor Cyan
Write-Host ""
Write-Host "Waiting for installation to complete (this may take 2-3 minutes)..." -ForegroundColor Yellow

Start-Sleep -Seconds 10

# Poll for completion
$maxAttempts = 30
$attempt = 0
$completed = $false

while ($attempt -lt $maxAttempts -and -not $completed) {
    $attempt++

    $status = aws ssm get-command-invocation `
      --region $REGION `
      --command-id $commandId `
      --instance-id $INSTANCE_ID `
      --query 'Status' `
      --output text

    Write-Host "  Attempt $attempt/$maxAttempts - Status: $status" -ForegroundColor Gray

    if ($status -eq "Success") {
        $completed = $true
        Write-Host ""
        Write-Host "Installation completed successfully!" -ForegroundColor Green

        # Show output
        Write-Host ""
        Write-Host "Installation output:" -ForegroundColor Cyan
        $output = aws ssm get-command-invocation `
          --region $REGION `
          --command-id $commandId `
          --instance-id $INSTANCE_ID `
          --query 'StandardOutputContent' `
          --output text
        Write-Host $output -ForegroundColor White

        break
    }
    elseif ($status -eq "Failed") {
        Write-Host ""
        Write-Host "Installation failed!" -ForegroundColor Red

        $error = aws ssm get-command-invocation `
          --region $REGION `
          --command-id $commandId `
          --instance-id $INSTANCE_ID `
          --query 'StandardErrorContent' `
          --output text
        Write-Host "Error: $error" -ForegroundColor Red
        exit 1
    }
    elseif ($status -eq "InProgress" -or $status -eq "Pending") {
        Start-Sleep -Seconds 10
    }
    else {
        Write-Host "  Unknown status: $status" -ForegroundColor Yellow
        Start-Sleep -Seconds 10
    }
}

if (-not $completed) {
    Write-Host ""
    Write-Host "Installation timed out or status unclear" -ForegroundColor Red
    Write-Host "Check AWS Console for command ID: $commandId" -ForegroundColor Yellow
    exit 1
}

# Verify AWS CLI is installed
Write-Host ""
Write-Host "Verifying AWS CLI installation..." -ForegroundColor Yellow

$testCommandId = aws ssm send-command `
  --region $REGION `
  --instance-ids $INSTANCE_ID `
  --document-name "AWS-RunShellScript" `
  --parameters commands="aws --version","python3 --version","which unzip" `
  --output text `
  --query 'Command.CommandId'

Start-Sleep -Seconds 5

$testOutput = aws ssm get-command-invocation `
  --region $REGION `
  --command-id $testCommandId `
  --instance-id $INSTANCE_ID `
  --query 'StandardOutputContent' `
  --output text

Write-Host $testOutput -ForegroundColor White

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Instance is now ready for deployment." -ForegroundColor Green
Write-Host "Run your CD pipeline to deploy the application." -ForegroundColor Cyan
