"use client";
import * as React from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  BarChart,
  Bar,
} from "recharts";

export default function Charts({ monthly }: { monthly: any[] }) {
  const lineData = (monthly ?? []).map((m: any) => ({ m: m.month, bal: m.balance }));
  const barData = (monthly ?? []).map((m: any) => ({ m: m.month, principal: m.principal, interest: m.interest }));
  return (
    <div className="mt-4 grid gap-4 md:grid-cols-2">
      <div className="h-64 w-full will-change-transform">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={lineData}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
            <XAxis dataKey="m" stroke="rgba(255,255,255,0.5)" />
            <YAxis stroke="rgba(255,255,255,0.5)" />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="bal" name="Balance" stroke="#60a5fa" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="h-64 w-full will-change-transform">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={barData}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
            <XAxis dataKey="m" stroke="rgba(255,255,255,0.5)" />
            <YAxis stroke="rgba(255,255,255,0.5)" />
            <Tooltip />
            <Legend />
            <Bar dataKey="principal" stackId="a" fill="#34d399" name="Principal" />
            <Bar dataKey="interest" stackId="a" fill="#f472b6" name="Interest" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
