#!/bin/bash
set -e

# Deploy script for Alibaba Cloud Function Compute (custom container)
# Prerequisites:
#   - Alibaba Cloud CLI (aliyun) installed and configured
#   - Docker installed
#   - ACR (Container Registry) instance created
#   - Function Compute service created

REGION="${DEPLOY_REGION:-sg}"
ACR_REGISTRY="${ACR_REGISTRY:-registry.sg.cr.aliyuncs.com}"
ACR_NAMESPACE="${ACR_NAMESPACE:-talentpilot}"
IMAGE_NAME="talentpilot"
IMAGE_TAG="latest"
FULL_IMAGE="${ACR_REGISTRY}/${ACR_NAMESPACE}/${IMAGE_NAME}:${IMAGE_TAG}"

echo "=== Building Docker image ==="
docker build -t "${IMAGE_NAME}:${IMAGE_TAG}" -f deploy/Dockerfile .

echo "=== Tagging for ACR ==="
docker tag "${IMAGE_NAME}:${IMAGE_TAG}" "${FULL_IMAGE}"

echo "=== Pushing to ACR ==="
docker push "${FULL_IMAGE}"

echo "=== Image pushed to: ${FULL_IMAGE} ==="
echo ""
echo "Next steps:"
echo "1. Go to Alibaba Cloud Console → Function Compute → Create Function"
echo "2. Choose 'Custom Container' runtime"
echo "3. Set image URI to: ${FULL_IMAGE}"
echo "4. Set port to: 9000"
echo "5. Configure environment variables:"
echo "   - QWEN_API_KEY=<your-key>"
echo "   - QWEN_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
echo "   - ALIYUN_SMTP_USER=<your-smtp-user>"
echo "   - ALIYUN_SMTP_PASS=<your-smtp-pass>"
echo "   - SMTP_SENDER=noreply@yourdomain.com"
echo "6. Create HTTP trigger"
echo "7. Test the endpoint"
