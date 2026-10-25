import { handleUpload } from '@vercel/blob/client';

const allowedContentTypes = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/plain'
];
const allowedExtensions = new Set(['pdf', 'docx', 'txt']);

export default async function handler(request, response) {
  if (request.method !== 'POST') {
    response.setHeader('Allow', 'POST');
    return response.status(405).json({ error: 'Method not allowed.' });
  }

  try {
    const result = await handleUpload({
      body: request.body,
      request,
      onBeforeGenerateToken: async (pathname) => {
        const segments = pathname.split('/');
        const extension = pathname.split('.').pop().toLowerCase();
        if (
          !pathname.startsWith('training-materials/') ||
          segments.length !== 3 ||
          segments.includes('..') ||
          segments.includes('.') ||
          !allowedExtensions.has(extension)
        ) {
          throw new Error('Invalid upload path.');
        }

        return {
          allowedContentTypes,
          maximumSizeInBytes: 25 * 1024 * 1024
        };
      },
      onUploadCompleted: async () => {}
    });

    return response.status(200).json(result);
  } catch (error) {
    console.error('Failed to authorize Blob upload.', error);
    return response.status(400).json({ error: 'Could not authorize this file upload.' });
  }
}
