const express = require('express');
const app = express();

app.get('/healthz', (req, res) => {
  res.json({ status: 'ok', service: 'pdf-service' });
});

app.post('/render', (req, res) => {
  res.status(501).json({ error: { code: 'not_implemented', message: 'PDF rendering will be implemented in Week 5' } });
});

const port = process.env.PORT || 4000;
app.listen(port, () => console.log(`pdf-service listening on ${port}`));
