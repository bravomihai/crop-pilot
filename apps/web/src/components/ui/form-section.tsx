import type { ReactNode } from "react";

export default function FormSection({
  id,
  step,
  title,
  description,
  children,
}: {
  id: string;
  step: string;
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <section className="panel" aria-labelledby={`${id}-title`}>
      <header className="panel-heading">
        <span className="step-number" aria-hidden="true">
          {step}
        </span>
        <h3 id={`${id}-title`}>{title}</h3>
      </header>
      <p className="section-description">{description}</p>
      {children}
    </section>
  );
}
