<script setup>
import StaticHeader from '../components/layout/StaticHeader.vue'
</script>

<template>
  <StaticHeader />
  <div class="wrap" style="max-width:74ch;padding-block:var(--sp8)">
    <h1 style="margin-bottom:var(--sp2)">Getting started</h1>
    <p class="sub" style="margin-bottom:var(--sp6)">
      What a tenant is, what a slug is, and why creating a community does not immediately let you
      raise a request or join a group. Five minutes, read once.
    </p>

    <section class="card">
      <h2>A tenant is one community</h2>
      <p style="font-size:14.5px;line-height:1.7;color:var(--ink-2)">
        A <b>tenant</b> is a single community on Quorum, a housing society, a campus club, an NGO,
        whatever. Every tenant has a <b>slug</b>: a short, lowercase-with-dashes identifier,
        <code class="mono">vaikunth-heights</code> or <code class="mono">riverside-coding-club</code>.
        The slug becomes part of every URL for that community
        (<code class="mono">/t/your-slug/dashboard</code>) and it is what people use to find and
        join it. Pick something short and recognizable, usually the building or society name, or
        the club name.
      </p>
    </section>

    <section class="card" style="margin-top:var(--sp5)">
      <h2>Two ways to start, both from Onboard</h2>
      <p style="font-size:14.5px;line-height:1.7;color:var(--ink-2)">
        <router-link class="tl" to="/onboard">Onboard</router-link> is a Join / Create toggle.
      </p>
      <div class="row r-32" style="margin-top:var(--sp3)">
        <div>
          <h3 style="margin-bottom:var(--sp2)">Create</h3>
          <p style="font-size:14px;line-height:1.65;color:var(--ink-2)">
            Name the community, pick its slug, pick a vertical (housing society, campus club, NGO,
            alumni chapter, housing cooperative, sports club, professional guild). The vertical sets
            default vocabulary and which Insight Packs are on by default. Only housing society and
            campus club have real demo data behind them right now; the rest work but start empty.
            Then give your own name, email and password. Any real email works, there is no domain
            restriction. This makes you that tenant's <b>TENANT_ADMIN</b>.
          </p>
        </div>
        <div>
          <h3 style="margin-bottom:var(--sp2)">Join</h3>
          <p style="font-size:14px;line-height:1.65;color:var(--ink-2)">
            Enter an existing tenant's slug. You are handed to signup with that slug prefilled, and
            you pick your own name, email and password there too. Any real email works. This makes
            you a <b>MEMBER</b> of that tenant.
          </p>
        </div>
      </div>
    </section>

    <div class="callout callout-info" style="margin-top:var(--sp5)">
      <span>
        <b>Admin is oversight, not participation.</b>
        TENANT_ADMIN gives you the approvals queue, tenant-wide request and ledger visibility,
        settings, and the ability to enable Insight Packs. It does not give you a Member row.
        A TENANT_ADMIN cannot raise a request, join or lead a group, register for an event, or cast
        a ballot, those all require a real Member account, which only a MEMBER signup creates.
        Email is globally unique across the whole platform, one account per email, not one per
        tenant, so if you want to both administer a tenant and participate in it, you need
        <b>two accounts with two different emails</b> against the same slug: one signed up as
        TENANT_ADMIN, one signed up as MEMBER. This is not a bug, it is the access model.
      </span>
    </div>

    <section class="card" style="margin-top:var(--sp5)">
      <h2>Getting real members in</h2>
      <p style="font-size:14.5px;line-height:1.7;color:var(--ink-2)">
        Once a tenant exists, share its slug with the actual community. Anyone can go to
        <router-link class="tl" to="/onboard">Onboard</router-link>, choose Join, enter the slug,
        and sign up as a MEMBER. There is no invite-link or email-invite system yet, sharing the
        slug is the real mechanism, and the Join flow's own output is a signup link with
        <code class="mono">?tenant=your-slug</code> already prefilled, which is worth passing along
        directly.
      </p>
    </section>

    <section class="card" style="margin-top:var(--sp5)">
      <h2>The first group</h2>
      <p style="font-size:14.5px;line-height:1.7;color:var(--ink-2)">
        Groups, a maintenance committee, a social committee, a club chapter, are created by a
        <b>MEMBER</b>, not an admin. Whoever creates a group becomes its leader automatically. So
        bootstrapping a real tenant looks like this:
      </p>
      <ol style="padding-left:1.2em;margin-top:var(--sp3);display:flex;flex-direction:column;gap:8px;font-size:14px;color:var(--ink-2)">
        <li>Create the tenant and get a TENANT_ADMIN account.</li>
        <li>Sign up a second account as MEMBER against the same slug, either your own second email or a real resident's.</li>
        <li>That member creates the first group.</li>
        <li>Other members join the group; the leader approves them.</li>
        <li>Requests, events and ledger activity now flow through the group.</li>
      </ol>
    </section>

    <div class="pull" style="margin-top:var(--sp6)">
      Want to look around before setting any of this up? The README's
      <a href="https://github.com/1mystic/Quorum#running-it" target="_blank" rel="noreferrer">Running it</a>
      section has ready-made demo accounts, both a local seed set and a live set on the project's
      real database, admin and member, for both demo verticals.
    </div>

    <div style="margin-top:var(--sp7);display:flex;gap:var(--sp5)">
      <router-link class="tl" to="/onboard">Join or create a tenant</router-link>
      <router-link class="tl" to="/methods">Read the method cards</router-link>
    </div>
  </div>
</template>
