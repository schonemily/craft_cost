const express = require('express');
const PDFDocument = require('pdfkit');
const app = express();
const SCHEDULE_LIMIT = Number(process.env.SCHEDULE_LIMIT || 24);

app.use(express.json({ limit: '1mb' }));

app.get('/healthz', (req, res) => {
  res.json({ status: 'ok', service: 'pdf-service' });
});

function fmtCurrency(n) {
  const v = Number(n || 0);
  return `$${v.toFixed(2)}`;
}

function drawTable(doc, headers, rows, colWidths, opts = {}) {
  const marginL = doc.page.margins.left || 50;
  const marginR = doc.page.margins.right || 50;
  const maxWidth = doc.page.width - marginL - marginR;
  const sumWidth = colWidths.reduce((a, b) => a + b, 0);
  const scale = sumWidth > 0 ? Math.min(1, maxWidth / sumWidth) : 1;
  const widths = colWidths.map(w => Math.floor(w * scale));
  const totalWidth = widths.reduce((a, b) => a + b, 0);
  const rowH = 20;
  const align = opts.align || headers.map(() => 'left');
  let y = doc.y + 6;
  let x0 = marginL;

  function ensureSpace(h) {
    const bottom = doc.page.height - (doc.page.margins.bottom || 50);
    if (y + h > bottom) {
      doc.addPage();
      y = (doc.page.margins.top || 50);
    }
  }

  // Header
  ensureSpace(rowH);
  doc.save();
  doc.rect(x0, y, totalWidth, rowH).fill('#f0f0f0');
  doc.fillColor('#000').font('Helvetica-Bold').fontSize(10);
  let x = x0;
  headers.forEach((h, i) => {
    doc.text(String(h), x + 6, y + 5, { width: widths[i] - 12, align: align[i] || 'left' });
    x += widths[i];
  });
  doc.restore();
  doc.strokeColor('#cccccc').lineWidth(0.5).rect(x0, y, totalWidth, rowH).stroke();
  y += rowH;

  // Rows
  doc.font('Helvetica').fontSize(10).fillColor('#000');
  rows.forEach((r) => {
    ensureSpace(rowH);
    doc.strokeColor('#e5e7eb').lineWidth(0.5).rect(x0, y, totalWidth, rowH).stroke();
    let cx = x0;
    r.forEach((cell, i) => {
      const text = (cell === null || cell === undefined) ? '' : String(cell);
      doc.text(text, cx + 6, y + 5, { width: widths[i] - 12, align: align[i] || 'left' });
      cx += widths[i];
    });
    y += rowH;
  });

  doc.moveDown();
  doc.y = y;
}

function section(doc, name, r) {
  if (!r) return;
  doc.moveDown().fontSize(14).font('Helvetica-Bold').text(String(name).toUpperCase());
  doc.font('Helvetica');

  // Summary table
  drawTable(
    doc,
    ['Metric', 'Value'],
    [
      ['Months', String(r.months || 0)],
      ['Interest paid', fmtCurrency(r.interest_paid)],
      ['Total paid', fmtCurrency(r.total_paid)],
    ],
    [200, 200],
    { align: ['left', 'right'] }
  );

  // Debts summary table
  if (Array.isArray(r.debts) && r.debts.length) {
    doc.fontSize(12).font('Helvetica-Bold').text('Debts summary');
    doc.font('Helvetica');
    const debtsRows = r.debts.slice(0, 20).map(d => [
      d.name || '',
      String(d.months || 0),
      fmtCurrency(d.interest_paid),
      fmtCurrency(d.total_paid),
    ]);
    drawTable(
      doc,
      ['Debt', 'Months', 'Interest', 'Total Paid'],
      debtsRows,
      [220, 70, 100, 100],
      { align: ['left', 'right', 'right', 'right'] }
    );
  }

  // Monthly schedule table (first N months)
  if (Array.isArray(r.monthly) && r.monthly.length) {
    doc.fontSize(12).font('Helvetica-Bold').text(`Schedule (first ${SCHEDULE_LIMIT} months)`);
    doc.font('Helvetica');
    const rows = r.monthly.slice(0, SCHEDULE_LIMIT).map(m => [
      String(m.month ?? ''),
      fmtCurrency(m.balance),
      fmtCurrency(m.interest),
      fmtCurrency(m.principal),
    ]);
    drawTable(
      doc,
      ['Month', 'Balance', 'Interest', 'Principal'],
      rows,
      [70, 120, 120, 120],
      { align: ['right', 'right', 'right', 'right'] }
    );
  }
}

app.post('/render', (req, res) => {
  try {
    const { title, snowball, avalanche, strategy } = req.body || {};
    res.setHeader('Content-Type', 'application/pdf');
    res.setHeader('Content-Disposition', 'inline; filename="debt-plan.pdf"');
    const doc = new PDFDocument({ size: 'A4', margin: 60 });
    doc.pipe(res);
    // Footer on each page (simple, avoid line wraps)
    const drawFooter = () => {
      const bottomY = doc.page.height - (doc.page.margins.bottom || 50);
      const footerY = bottomY - 20;
      const leftX = doc.page.margins.left;
      const rightW = doc.page.width - doc.page.margins.left - doc.page.margins.right;
      const t = String(title || 'Debt Payoff Plan');
      doc.font('Helvetica').fontSize(9).fillColor('#6b7280');
      doc.text(t, leftX, footerY, { width: rightW / 2, align: 'left', lineBreak: false });
      doc.text(`Page ${doc.page.number}`, leftX + rightW / 2, footerY, { width: rightW / 2, align: 'right', lineBreak: false });
      doc.fillColor('#000');
    };
    drawFooter();
    doc.on('pageAdded', drawFooter);

    doc.fontSize(18).font('Helvetica-Bold').text(String(title || 'Debt Payoff Plan'));
    doc.moveDown();
    if (snowball || avalanche || strategy) {
      if (snowball) section(doc, 'Snowball', snowball);
      if (avalanche) section(doc, 'Avalanche', avalanche);
      if (strategy && !snowball && !avalanche) section(doc, strategy.strategy || 'Result', strategy);
    } else {
      doc.font('Helvetica').fontSize(12).text('No plan data provided.');
    }
    doc.end();
  } catch (e) {
    console.error('render error', e);
    res.status(500).json({ error: { code: 'render_error', message: String(e?.message || e) } });
  }
});

const port = process.env.PORT || 4000;
app.listen(port, () => console.log(`pdf-service listening on ${port}`));
