import { Link } from "../router";
import { Icon } from "../components/Icon";

const helpTopics = [
  { icon: "regulations", category: "KNOWLEDGE", title: "Regulatory Library", description: "Upload regulatory PDFs, import documents from URLs, and manage your indexed regulatory knowledge base.", href: "#/regulations", action: "Explore regulations" },
  { icon: "ask", category: "AI ASSISTANCE", title: "AI Assistant", description: "Ask questions about regulations, understand compliance requirements, and get answers grounded in your available documents.", href: "#/ask", action: "Start a conversation" },
  { icon: "business", category: "GETTING STARTED", title: "Business Profile", description: "Configure your organization details to help identify potentially applicable regulatory obligations.", href: "#/business", action: "Set up your profile" },
  { icon: "assessments", category: "COMPLIANCE", title: "Assessments", description: "Review applicable requirements, evaluate compliance status, and track assessment findings.", href: "#/assessments", action: "View assessments" },
  { icon: "risk", category: "ANALYTICS", title: "Risk & Reports", description: "Review identified risks, understand compliance gaps, and access available reports.", href: "#/risk", action: "Explore risk dashboard" },
  { icon: "alerts", category: "MONITORING", title: "Alerts & Reminders", description: "Review compliance alerts, follow up on reminders, and stay aware of important tasks.", href: "#/reminders", action: "View alerts" },
  { icon: "profile", category: "ACCOUNT", title: "Profile & Settings", description: "Manage your account information and configure the settings available in your workspace.", href: "#/profile", action: "Manage account" },
];

const faqs = [
  { question: "How do I add a regulation?", answer: "Open Regulatory Library, choose the Regulations section, and upload a supported PDF or TXT file. You can also use the URL import option when available. Follow the indexing status to confirm processing." },
  { question: "Why should I complete my Business Profile?", answer: "Your business information helps RegLens AI evaluate which regulatory requirements may apply to your organization. Incomplete information can limit the usefulness of applicability reviews." },
  { question: "How does the AI Assistant answer questions?", answer: "The assistant uses the regulatory knowledge available to your workspace and the configured AI retrieval system. Check cited sources and the underlying regulation before relying on an answer for a compliance decision." },
  { question: "Where can I review compliance risks?", answer: "Open Risk & Reports to access the risk dashboard and available reports. The information shown depends on your business profile, indexed regulations, assessments, and available findings." },
  { question: "What should I do if a document fails to process?", answer: "Check that the file is supported and readable, then retry the upload. If the problem continues, contact your workspace administrator with the document name and any displayed error message." },
];

export function HelpPage() {
  return (
    <main className="help-page page">
      <header className="help-page__header">
        <div className="help-page__eyebrow"><Icon name="help" /> HELP CENTER</div>
        <h1>How can we help?</h1>
        <p>Find guidance on using RegLens AI to organize regulations, understand compliance obligations, and manage risks.</p>
      </header>

      <section className="help-welcome">
        <div className="help-welcome__icon"><Icon name="compliance" /></div>
        <div className="help-welcome__content">
          <h2>New to RegLens AI?</h2>
          <p>Start by completing your Business Profile, adding your regulatory documents, and reviewing your compliance assessments.</p>
        </div>
        <Link className="help-welcome__action" href="#/business">Get started <span aria-hidden="true">→</span></Link>
      </section>

      <section className="help-section">
        <div className="help-section__heading"><div><h2>Explore help topics</h2><p>Quick guidance for the main features in your workspace.</p></div></div>
        <div className="help-topics-grid">
          {helpTopics.map((topic) => (
            <article className="help-topic-card" key={topic.title}>
              <div className="help-topic-card__top"><span className="help-topic-card__icon"><Icon name={topic.icon} /></span><span className="help-topic-card__category">{topic.category}</span></div>
              <h3>{topic.title}</h3><p>{topic.description}</p>
              <Link className="help-topic-card__link" href={topic.href}>{topic.action}<span aria-hidden="true"> →</span></Link>
            </article>
          ))}
        </div>
      </section>

      <section className="help-section help-faq">
        <div className="help-section__heading"><div><h2>Frequently asked questions</h2><p>Answers to common questions about your compliance workflow.</p></div></div>
        <div className="help-faq__list">
          {faqs.map((faq) => <details className="help-faq__item" key={faq.question}><summary><span>{faq.question}</span><span className="help-faq__plus" aria-hidden="true">+</span></summary><p>{faq.answer}</p></details>)}
        </div>
      </section>

      <section className="help-support">
        <div className="help-support__icon"><Icon name="message" /></div>
        <div className="help-support__content"><h2>Still need help?</h2><p>Contact your workspace administrator if you need assistance with access, permissions, document processing, or account setup.</p></div>
        <Link className="help-support__back" href="#/home">Back to dashboard</Link>
      </section>
    </main>
  );
}
