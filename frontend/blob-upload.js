import { upload } from '@vercel/blob/client';

window.uploadTrainingMaterialDirect = async (file, metadata) => {
  const safeName = file.name.replace(/[^\w.-]+/g, '_').replace(/^\.+/, '') || 'training-material';
  const extension = safeName.split('.').pop().toLowerCase();
  const contentTypes = {
    pdf: 'application/pdf',
    docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    txt: 'text/plain'
  };
  const contentType = contentTypes[extension];
  if (!contentType) {
    throw new Error('Only PDF, DOCX, and TXT files are supported.');
  }

  const pathname = `training-materials/${crypto.randomUUID()}/${safeName}`;
  const uploaded = await upload(pathname, file, {
    access: 'private',
    contentType,
    handleUploadUrl: '/api/blob-upload'
  });

  const response = await fetch('/api/materials/process-blob', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      pathname: uploaded.pathname,
      skill_id: metadata.skillId,
      title: metadata.title,
      uploaded_by: metadata.uploadedBy
    })
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to process uploaded document.');
  }

  return response.json();
};
