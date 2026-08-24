/**
 * Guided tour — same interaction model as Outturn (driver.js spotlight).
 * Pages set window.COMPLIANCE_TOUR_STEPS before this script runs, or use built-ins.
 */
(function () {
  const SEEN_KEY = "agrinexus_compliance_tour_seen";
  const START_EVENT = "compliance:start-tour";

  function presentSteps(steps) {
    return (steps || []).filter(function (s) {
      if (!s.element) return true;
      if (typeof s.element !== "string") return true;
      return !!document.querySelector(s.element);
    });
  }

  function addSkipButton(popover, d) {
    if (popover.footerButtons.querySelector(".outturn-skip-btn")) return;
    const skip = document.createElement("button");
    skip.type = "button";
    skip.textContent = "Skip";
    skip.className = "driver-popover-prev-btn outturn-skip-btn";
    skip.addEventListener("click", function () {
      d.destroy();
    });
    popover.footerButtons.insertBefore(skip, popover.nextButton);
  }

  const PAGE_STEPS = {
    home: [
      {
        popover: {
          title: "What this product is",
          description:
            "AgriNexus Compliance is a closed loop for 2026 ESA pesticide-label steps: plan one field, remind by SMS, confirm in plain language, keep a record — and show the partner who followed through. Same engine as Outturn / AgriNexus; US label domain.",
          showButtons: ["next", "close"],
          showProgress: false,
          nextBtnText: "Show me",
          onPopoverRender: function (popover, opts) {
            addSkipButton(popover, opts.driver);
          },
        },
      },
      {
        element: '[data-tour="home-hero"]',
        popover: {
          title: "You are the partner",
          description:
            "Imagine Boone County extension or a PAT training class. You care about a cohort of applicators — not a single static form.",
        },
      },
      {
        element: '[data-tour="cohort-stats"]',
        popover: {
          title: "Follow-through at a glance",
          description:
            "How many confirmed, how many still waiting. This is what Outturn shows for India cohorts; here it is ESA label work.",
        },
      },
      {
        element: '[data-tour="cohort-board"]',
        popover: {
          title: "The roster",
          description:
            "Example applicators plus any live session you run. Open Inbox on a live row to see the SMS thread.",
        },
      },
      {
        element: '[data-tour="roles"]',
        popover: {
          title: "Two roles, one loop",
          description:
            "Partner watches the board. Applicator checks a field, gets SMS, replies, downloads a record. Next: try Applicator check.",
        },
      },
    ],
    check: [
      {
        popover: {
          title: "Step 1 — Plan",
          description:
            "One question for an extension audience: can this applicator spray this Boone field with Liberty ULTRA? Points, weather, and bulletin actions — in plain language.",
          showButtons: ["next", "close"],
          showProgress: false,
          nextBtnText: "Show me",
          onPopoverRender: function (popover, opts) {
            addSkipButton(popover, opts.driver);
          },
        },
      },
      {
        element: '[data-tour="summary"]',
        popover: {
          title: "Sample field pack",
          description:
            "Real EPA Reg. No. 7969-500 and August 2026 bulletin fixtures, marked as sample educational data — not a fake DEMO number.",
        },
      },
      {
        element: '[data-tour="check-cta"]',
        popover: {
          title: "Check this application",
          description:
            "Pick a forecast scenario (calm vs windy) to show the weather gate, then run the plan. Confirm and Receipt unlock after.",
        },
      },
    ],
    confirm: [
      {
        popover: {
          title: "Step 2 — Confirm",
          description:
            "SMS-style reminder out; applicator replies in their own words. Simulate day-after reminder (T+24) for the video.",
          showButtons: ["next", "close"],
          showProgress: false,
          nextBtnText: "Show me",
          onPopoverRender: function (popover, opts) {
            addSkipButton(popover, opts.driver);
          },
        },
      },
      {
        element: '[data-tour="sms-thread"]',
        popover: {
          title: "What they would text",
          description:
            "Placeholder examples like keeping a creek-side buffer — not keyword DONE.",
        },
      },
    ],
    receipt: [
      {
        popover: {
          title: "Step 3 — Receipt",
          description:
            "Standalone record for screenshots and the outreach one-pager: status, points, weather, timeline, PDF download.",
          showButtons: ["next", "close"],
          showProgress: false,
          nextBtnText: "Show me",
          onPopoverRender: function (popover, opts) {
            addSkipButton(popover, opts.driver);
          },
        },
      },
      {
        element: '[data-tour="download-pdf"]',
        popover: {
          title: "Download the PDF",
          description: "Primary takeaway for outreach emails.",
        },
      },
    ],
  };

  function getSteps() {
    if (window.COMPLIANCE_TOUR_STEPS && window.COMPLIANCE_TOUR_STEPS.length) {
      return presentSteps(window.COMPLIANCE_TOUR_STEPS);
    }
    const page = document.body.getAttribute("data-tour-page") || "home";
    return presentSteps(PAGE_STEPS[page] || PAGE_STEPS.home);
  }

  function startTour() {
    if (!window.driver || !window.driver.js || !window.driver.js.driver) {
      console.warn("driver.js not loaded");
      return;
    }
    const steps = getSteps();
    if (!steps.length) return;
    const d = window.driver.js.driver({
      showProgress: true,
      progressText: "{{current}} of {{total}}",
      allowClose: true,
      overlayColor: "#1a1714",
      overlayOpacity: 0.55,
      stagePadding: 6,
      stageRadius: 10,
      popoverClass: "outturn-tour",
      nextBtnText: "Next",
      prevBtnText: "Back",
      doneBtnText: "Done",
      onDestroyed: function () {
        try {
          localStorage.setItem(SEEN_KEY, "1");
        } catch (e) {
          /* ignore */
        }
      },
      steps: steps,
    });
    d.drive();
  }

  window.startComplianceTour = startTour;
  window.addEventListener(START_EVENT, startTour);

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-tour-trigger]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        startTour();
      });
    });

    var auto = document.body.getAttribute("data-tour-auto");
    if (auto === "false") return;
    var seen = "0";
    try {
      seen = localStorage.getItem(SEEN_KEY) || "0";
    } catch (e) {
      seen = "1";
    }
    if (seen === "1") return;
    if (window.innerWidth < 768) return;
    window.setTimeout(startTour, 700);
  });
})();
