
import { useEffect, useState, type FormEvent } from "react";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  ErrorNotice,
  FormField,
  Input,
  Loader,
  Page,
  PageHeader,
  Select,
  Textarea,
} from "../components/ui";
import { useFeedback } from "../components/feedback";
import { useResource } from "../hooks/useResource";
import { api } from "../services/api";
import type {
  CompanyResponse,
  Document,
  Registration,
} from "../types/api";

type Form = Record<string, string>;

// Required business information
const REQUIRED_FIELDS = new Set([
  "legal_name",
  "entity_type",
  "industry",
  "activity",
  "state",
  "turnover",
  "employees",
  "operations_scope",
  "customer_type",
  "supply_type",
  "import_export",
  "regulated_financial",
  "listed_entity",
]);

const TEXT: Array<[string, string, string?]> = [
  ["legal_name", "Legal name"],
  ["industry", "Industry"],
  ["activity", "Main business activity"],
  ["established_year", "Established year", "number"],
  ["branches", "Branches", "number"],
  ["gstin", "GSTIN"],
  ["pan", "PAN"],
];

const LISTS: Array<[string, string]> = [
  ["business_types", "Business types"],
  ["licences", "Licences"],
  ["data_handled", "Data handled (e.g. Aadhaar, PAN, health)"],
  ["securities_activities", "Securities activities"],
  ["other_activities", "Other activities"],
];

const emptyReg = (): Registration => ({
  registration_type: "",
  required_status: "unknown",
  status: "unknown",
  number: "",
  effective_date: null,
  expiry_date: null,
  document_id: null,
});

function toForm(company: CompanyResponse["company"]): Form {
  const f: Form = {};

  for (const [k, v] of Object.entries(company)) {
    if (k === "registrations") continue;

    f[k] = Array.isArray(v)
      ? (v as string[]).join(", ")
      : v == null
        ? ""
        : String(v);
  }

  // Country is always India.
  f.country = "India";

  return f;
}

export function BusinessPage() {
  const resource = useResource<CompanyResponse>("/company");
  const docs = useResource<Document[]>("/documents");
  const { run } = useFeedback();

  const [form, setForm] = useState<Form>({});
  const [regs, setRegs] = useState<Registration[]>([]);
  const [later, setLater] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Keep the persisted name as the baseline while the one-time change is available.
  const [lockedLegalName, setLockedLegalName] = useState("");
  const [legalNameChangeUsed, setLegalNameChangeUsed] = useState(false);
  const [allowLegalNameChange, setAllowLegalNameChange] = useState(false);

  useEffect(() => {
    if (!resource.data) return;

    const company = resource.data.company;
    const initial = toForm(company);

    setForm(initial);
    setRegs(company.registrations ?? []);
    setLater(resource.data.profile.dismissed);

    // Assumes an existing legal name was previously saved.
    setLockedLegalName(initial.legal_name?.trim() ?? "");
    setLegalNameChangeUsed(resource.data.legal_name_change_used);
    setAllowLegalNameChange(false);
  }, [resource.data]);

  const legalNameLocked = Boolean(lockedLegalName) && (legalNameChangeUsed || !allowLegalNameChange);

  const set =
    (key: string) =>
    (e: { target: { value: string } }) => {
      if (key === "legal_name" && legalNameLocked) return;

      setForm((f) => ({
        ...f,
        [key]: e.target.value,
      }));

      setErrors((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });

      setSaved(false);
    };

  const setReg = (i: number, patch: Partial<Registration>) => {
    setRegs((r) =>
      r.map((x, j) =>
        j === i ? { ...x, ...patch } : x
      )
    );
    setSaved(false);
  };

  if (!resource.data) {
    return (
      <Page>
        <PageHeader
          title="Business Profile"
          description="These details help identify potentially relevant regulations."
        />
        <ErrorNotice error={resource.error} />
        <Loader />
      </Page>
    );
  }

  const { options, profile } = resource.data;

  function validate(): boolean {
    const next: Record<string, string> = {};

    for (const key of REQUIRED_FIELDS) {
      if (!form[key]?.trim()) {
        next[key] = "This field is required.";
      }
    }

    // GSTIN and PAN are optional.
    // Validate their format only when provided.
    const pan = form.pan?.trim().toUpperCase() ?? "";
    const gstin = form.gstin?.trim().toUpperCase() ?? "";

    if (pan && !/^[A-Z]{5}[0-9]{4}[A-Z]$/.test(pan)) {
      next.pan = "Enter a valid 10-character PAN.";
    }

    if (
      gstin &&
      !/^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/.test(gstin)
    ) {
      next.gstin = "Enter a valid 15-character GSTIN.";
    }

    setErrors(next);

    if (Object.keys(next).length > 0) {
      window.scrollTo({ top: 0, behavior: "smooth" });
      return false;
    }

    return true;
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!validate()) return;

    setBusy(true);

    try {
      const payload = {
        ...form,
        country: "India",
        legal_name: legalNameLocked
          ? lockedLegalName
          : form.legal_name.trim(),
        pan: form.pan?.trim().toUpperCase() ?? "",
        gstin: form.gstin?.trim().toUpperCase() ?? "",
        registrations: regs.filter((r) => r.registration_type),
        save_for_later: later ? "true" : "false",
      };

      const result = await run(
        () =>
          api<CompanyResponse>("/company", {
            method: "PUT",
            json: payload,
          }),
        "Business Profile saved"
      );

      if (result) {
        setSaved(true);
        resource.setData(result);

        const savedName = String(result.company.legal_name ?? "").trim();

        if (savedName) {
          setLockedLegalName(savedName);
        }
        setLegalNameChangeUsed(result.legal_name_change_used);
        setAllowLegalNameChange(false);
      }
    } finally {
      setBusy(false);
    }
  }

  const requiredLabel = (key: string, label: string) => (
    <>
      {label}
      {REQUIRED_FIELDS.has(key) && (
        <span
          style={{ color: "#dc2626", marginLeft: 4 }}
          aria-label="required"
        >
          *
        </span>
      )}
    </>
  );

  const text = ([key, label, type]: [
    string,
    string,
    string?,
  ]) => {
    const isLocked = key === "legal_name" && legalNameLocked;

    return (
      <div key={key}>
        <FormField label={requiredLabel(key, label)}>
          <Input
            type={type}
            value={form[key] ?? ""}
            onChange={set(key)}
            disabled={isLocked}
            required={REQUIRED_FIELDS.has(key)}
            aria-invalid={Boolean(errors[key])}
          />
        </FormField>

        {isLocked && !legalNameChangeUsed && (
          <Button type="button" variant="outline" size="sm" onClick={() => setAllowLegalNameChange(true)}>
            Use one-time legal name change
          </Button>
        )}
        {isLocked && legalNameChangeUsed && (
          <p className="muted" style={{ fontSize: 12, marginTop: 4 }}>
            Your one-time legal name change has been used. This name is permanently locked.
          </p>
        )}
        {!isLocked && Boolean(lockedLegalName) && (
          <p className="muted" style={{ fontSize: 12, marginTop: 4 }}>
            Saving a different name will use your one-time change.
            <Button type="button" variant="outline" size="sm" onClick={() => setAllowLegalNameChange(false)}>
              Cancel
            </Button>
          </p>
        )}

        {errors[key] && (
          <p style={{ color: "#dc2626", fontSize: 12 }}>
            {errors[key]}
          </p>
        )}
      </div>
    );
  };

  const choice = (
    key: string,
    label: string,
    values: string[]
  ) => (
    <div key={key}>
      <FormField label={requiredLabel(key, label)}>
        <Select
          value={form[key] ?? ""}
          onChange={set(key)}
          required={REQUIRED_FIELDS.has(key)}
        >
          <option value="">Choose…</option>
          {values.map((v) => (
            <option key={v} value={v}>
              {v}
            </option>
          ))}
        </Select>
      </FormField>

      {errors[key] && (
        <p style={{ color: "#dc2626", fontSize: 12 }}>
          {errors[key]}
        </p>
      )}
    </div>
  );

  const readyDocs = (docs.data ?? []).filter(
    (d) => d.status === "ready"
  );

  return (
    <Page>
      <PageHeader
        title="Business Profile"
        description="Your answers are saved to this workspace and used in applicability screening."
      />

      <Card>
        <p className="muted">
          Profile completion: {profile.completion_percent}%
          {profile.missing.length > 0 &&
            ` · missing: ${profile.missing.join(", ")}`}
        </p>

        <div className="bar" style={{ marginBottom: 20 }}>
          <i
            style={{
              width: `${profile.completion_percent}%`,
            }}
          />
        </div>

        <p className="muted" style={{ marginBottom: 20 }}>
          <span style={{ color: "#dc2626" }}>*</span>{" "}
          Indicates required information. PAN and GSTIN are optional.
        </p>

        <form onSubmit={save}>
          <div className="grid grid-2">
            {text(TEXT[0])}

            <FormField label="Country">
              <Input value="India" disabled />
            </FormField>

            {choice(
              "entity_type",
              "Entity type",
              options.entity_types
            )}

            {text(TEXT[1])}
            {text(TEXT[2])}

            {choice("state", "State", options.states)}
            {choice("turnover", "Annual turnover", options.turnover)}
            {choice("employees", "Employees", options.employees)}

            {choice(
              "operations_scope",
              "Operations",
              options.operations_scopes
            )}

            {choice(
              "customer_type",
              "Customers",
              options.customer_types
            )}

            {choice(
              "supply_type",
              "Supplies",
              options.supply_types
            )}

            {choice(
              "import_export",
              "Import or export?",
              options.yes_no_unknown
            )}

            {choice(
              "regulated_financial",
              "Regulated financial activity?",
              options.yes_no_unknown
            )}

            {choice(
              "listed_entity",
              "Listed entity?",
              options.yes_no_unknown
            )}

            {text(TEXT[3])}
            {text(TEXT[4])}
            {text(TEXT[5])}
            {text(TEXT[6])}
          </div>

          <div className="stack" style={{ marginTop: 16 }}>
            <FormField label="Business description">
              <Textarea
                value={form.description ?? ""}
                onChange={set("description")}
                maxLength={2000}
              />
            </FormField>

            <div className="grid grid-2">
              <FormField label="Import/export details">
                <Input
                  value={form.import_export_details ?? ""}
                  onChange={set("import_export_details")}
                />
              </FormField>

              <FormField label="Financial activity details">
                <Input
                  value={form.financial_activity_details ?? ""}
                  onChange={set("financial_activity_details")}
                />
              </FormField>

              <FormField label="Securities activity details">
                <Input
                  value={form.securities_activity_details ?? ""}
                  onChange={set("securities_activity_details")}
                />
              </FormField>

              {LISTS.map(([k, label]) => (
                <FormField key={k} label={label}>
                  <Input
                    value={form[k] ?? ""}
                    onChange={set(k)}
                  />
                </FormField>
              ))}
            </div>
          </div>

          <h3 style={{ marginTop: 28 }}>Registrations</h3>

          {regs.map((r, i) => (
            <div
              key={i}
              className="card"
              style={{
                marginBottom: 12,
                background: "var(--color-wash)",
              }}
            >
              <div className="grid grid-2">
                <FormField label="Registration type">
                  <Select
                    value={r.registration_type}
                    onChange={(e) =>
                      setReg(i, {
                        registration_type: e.target.value,
                      })
                    }
                  >
                    <option value="">Choose…</option>
                    {options.registration_types.map((x) => (
                      <option key={x}>{x}</option>
                    ))}
                  </Select>
                </FormField>

                <FormField label="Required?">
                  <Select
                    value={r.required_status}
                    onChange={(e) =>
                      setReg(i, {
                        required_status: e.target.value,
                      })
                    }
                  >
                    <option>unknown</option>
                    <option>required</option>
                    <option>not_required</option>
                  </Select>
                </FormField>

                <FormField label="Status">
                  <Select
                    value={r.status}
                    onChange={(e) =>
                      setReg(i, { status: e.target.value })
                    }
                  >
                    {[
                      "unknown",
                      "not_applied",
                      "pending",
                      "active",
                      "rejected",
                      "expired",
                      "not_applicable",
                    ].map((x) => (
                      <option key={x}>{x}</option>
                    ))}
                  </Select>
                </FormField>

                <FormField label="Registration number">
                  <Input
                    value={r.number}
                    onChange={(e) =>
                      setReg(i, { number: e.target.value })
                    }
                  />
                </FormField>

                <FormField label="Effective date">
                  <Input
                    type="date"
                    value={r.effective_date ?? ""}
                    onChange={(e) =>
                      setReg(i, {
                        effective_date: e.target.value || null,
                      })
                    }
                  />
                </FormField>

                <FormField label="Expiry date">
                  <Input
                    type="date"
                    value={r.expiry_date ?? ""}
                    onChange={(e) =>
                      setReg(i, {
                        expiry_date: e.target.value || null,
                      })
                    }
                  />
                </FormField>

                <FormField
                  label="Evidence document"
                  hint="From your Library"
                >
                  <Select
                    value={r.document_id ?? ""}
                    onChange={(e) =>
                      setReg(i, {
                        document_id: e.target.value
                          ? Number(e.target.value)
                          : null,
                      })
                    }
                  >
                    <option value="">None</option>
                    {readyDocs.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name}
                      </option>
                    ))}
                  </Select>
                </FormField>
              </div>

              <div className="actions">
                <Button
                  type="button"
                  size="sm"
                  variant="danger"
                  onClick={() => {
                    setRegs((x) =>
                      x.filter((_, j) => j !== i)
                    );
                    setSaved(false);
                  }}
                >
                  Remove
                </Button>
              </div>
            </div>
          ))}

          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => {
              setRegs((x) => [...x, emptyReg()]);
              setSaved(false);
            }}
          >
            Add registration
          </Button>

          <div style={{ marginTop: 24 }}>
            <Checkbox
              label="Save for later (don't remind me about missing details)"
              checked={later}
              onChange={(e) => {
                setLater(e.target.checked);
                setSaved(false);
              }}
            />
          </div>

          <div
            className="actions"
            style={{ justifyContent: "flex-start" }}
          >
            <Button type="submit" loading={busy}>
              Save Business Profile
            </Button>
          </div>
        </form>

        {saved && (
          <Alert>
            Saved. Start a new assessment to use the updated profile.
          </Alert>
        )}
      </Card>
    </Page>
  );
}
