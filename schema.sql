--
-- PostgreSQL database dump
--

\restrict KyKRf7DsOxbiSbhY1WiOq0regeV2XbrTArUFWYMHNi188lN5wpVwGGAb05Ph1Is

-- Dumped from database version 18.1
-- Dumped by pg_dump version 18.1

-- Started on 2026-02-06 22:01:30

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 220 (class 1259 OID 16399)
-- Name: communities; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.communities (
    community_id character varying NOT NULL,
    name character varying NOT NULL,
    category character varying,
    description character varying,
    member_count integer,
    city character varying,
    timezone character varying,
    embedding_id character varying,
    created_at timestamp without time zone
);


ALTER TABLE public.communities OWNER TO postgres;

--
-- TOC entry 219 (class 1259 OID 16389)
-- Name: match_tasks; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.match_tasks (
    task_id character varying NOT NULL,
    user_id character varying NOT NULL,
    status character varying,
    result json,
    error character varying,
    created_at timestamp without time zone,
    completed_at timestamp without time zone
);


ALTER TABLE public.match_tasks OWNER TO postgres;

--
-- TOC entry 221 (class 1259 OID 16410)
-- Name: user_profiles; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_profiles (
    user_id character varying NOT NULL,
    sanitized_bio character varying,
    enriched_tags json,
    city character varying,
    timezone character varying,
    last_updated timestamp without time zone
);


ALTER TABLE public.user_profiles OWNER TO postgres;

--
-- TOC entry 5020 (class 0 OID 16399)
-- Dependencies: 220
-- Data for Name: communities; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.communities (community_id, name, category, description, member_count, city, timezone, embedding_id, created_at) FROM stdin;
comm_001	Bangalore Python Developers	Programming	Community for Python developers in Bangalore	1200	Bangalore	Asia/Kolkata	vec_001	\N
comm_002	AI & ML Enthusiasts India	Artificial Intelligence	Discuss AI, ML, and deep learning trends	950	Bangalore	Asia/Kolkata	vec_002	\N
comm_003	Backend Engineers Hub	Backend	Backend system design and APIs	670	Bangalore	Asia/Kolkata	vec_003	\N
\.


--
-- TOC entry 5019 (class 0 OID 16389)
-- Dependencies: 219
-- Data for Name: match_tasks; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.match_tasks (task_id, user_id, status, result, error, created_at, completed_at) FROM stdin;
\.


--
-- TOC entry 5021 (class 0 OID 16410)
-- Dependencies: 221
-- Data for Name: user_profiles; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.user_profiles (user_id, sanitized_bio, enriched_tags, city, timezone, last_updated) FROM stdin;
\.


--
-- TOC entry 4867 (class 2606 OID 16407)
-- Name: communities communities_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.communities
    ADD CONSTRAINT communities_pkey PRIMARY KEY (community_id);


--
-- TOC entry 4865 (class 2606 OID 16397)
-- Name: match_tasks match_tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.match_tasks
    ADD CONSTRAINT match_tasks_pkey PRIMARY KEY (task_id);


--
-- TOC entry 4871 (class 2606 OID 16417)
-- Name: user_profiles user_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_profiles
    ADD CONSTRAINT user_profiles_pkey PRIMARY KEY (user_id);


--
-- TOC entry 4868 (class 1259 OID 16408)
-- Name: ix_communities_category; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_communities_category ON public.communities USING btree (category);


--
-- TOC entry 4869 (class 1259 OID 16409)
-- Name: ix_communities_city; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_communities_city ON public.communities USING btree (city);


--
-- TOC entry 4863 (class 1259 OID 16398)
-- Name: ix_match_tasks_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_match_tasks_user_id ON public.match_tasks USING btree (user_id);


-- Completed on 2026-02-06 22:01:30

--
-- PostgreSQL database dump complete
--

\unrestrict KyKRf7DsOxbiSbhY1WiOq0regeV2XbrTArUFWYMHNi188lN5wpVwGGAb05Ph1Is

