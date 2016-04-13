#!/usr/bin/env python2.7

import os
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, request, render_template, g, redirect, Response

tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)

DATABASEURI = "postgresql://ap3109:4652@w4111vm.eastus.cloudapp.azure.com/w4111"
# user = ; password = 4652;  DATABASEURI = "postgresql://user:password@w4111vm.eastus.cloudapp.azure.com/w4111"

engine = create_engine(DATABASEURI)

engine.execute("""CREATE TABLE IF NOT EXISTS test (
  id serial,
  name text
);""")

@app.before_request
def before_request():
  try:
    g.conn = engine.connect()
  except:
    print "uh oh, problem connecting to database"
    import traceback; traceback.print_exc()
    g.conn = None

@app.teardown_request
def teardown_request(exception):
  try:
    g.conn.close()
  except Exception as e:
    pass

@app.route('/')
def index():
  """
  request is a special object that Flask provides to access web request information:

  request.method:   "GET" or "POST"
  request.form:     if the browser submitted a form, this contains the data in the form
  request.args:     dictionary of URL arguments, e.g., {a:1, b:2} for http://localhost?a=1&b=2

  See its API: http://flask.pocoo.org/docs/0.10/api/#incoming-request-data
  """

  # DEBUG: this is debugging code to see what request looks like
  print request.args

  cursor = g.conn.execute("SELECT gene_name, SUM(num_mutations) as total_mutations FROM gene_page GROUP BY gene_name")
  gene_names = []
  for result in cursor:
    gene_names.append((result['gene_name'], result['total_mutations']))  # can also be accessed using result[0]
  cursor.close()
  gcontext = dict(genes = gene_names)


  query = "SELECT pdom_id, SUM(num_mutations) as total_mutations FROM protein_dom_pg GROUP BY pdom_id"
  cursor = g.conn.execute(query)
  pdoms = []
  for result in cursor:
    pdoms.append((result['pdom_id'], result['total_mutations']))  # can also be accessed using result[0]
  cursor.close()
  pcontext = dict(pdoms = pdoms)

  return render_template("index.html", genes = gene_names, pdoms = pdoms)

@app.route('/another')
def another():
  return render_template("another.html")

@app.route('/other')
def other():
  return render_template("another.html")


@app.route('/search_genes', methods=["POST", "GET"])
def search_genes():
  pdom = request.form['pdom']
  loc = request.form['location']
  min_mut = request.form['min_mut']
  max_mut = request.form['max_mut']

  error = 0
  if not all(char.isdigit() for char in loc + min_mut + max_mut) or len(pdom) > 8:
    error = 1

  genes_results = []
  if not error:
    sql_query = "SELECT gene_name, SUM(num_mutations) as total_mutations FROM gene_page"

    conditions = []
    if pdom:
      conditions.append('pdom_id = \'%s\'' % pdom)
    if loc:
      conditions.append('location = %s' % loc)
    if min_mut:
      conditions.append('num_mutations > %s' % min_mut)
    if max_mut:
      conditions.append('num_mutations < %s' % max_mut)

    cond_line = ""
    if len(conditions) == 0:
      pass
    elif len(conditions) == 1:
      cond_line += ' WHERE ' + conditions[0]
    else:
      cond_line = ' WHERE ' + (' AND ').join(conditions)

    sql_query += cond_line
    sql_query += ' GROUP BY gene_name;'

    print sql_query
    cursor = g.conn.execute(sql_query)

    for result in cursor:
      genes_results.append((result['gene_name'], result['total_mutations']))  
    cursor.close()

  print genes_results
  return render_template("another.html", genes = genes_results)

@app.route('/search_pdoms', methods=["POST", "GET"])
def search_pdoms():
  gene = request.form['gene']
  min_mut = request.form['min_mut']
  max_mut = request.form['max_mut']

  error = 0
  if len(gene) > 8:
    error = 1
  if not all(char.isdigit() for char in min_mut + max_mut):
    error = 1

  pdom_results = []
  if not error:
    sql_query = "SELECT pdom_id, SUM(num_mutations) as total_mutations FROM protein_dom_pg"

    conditions = []
    having_conditions = []
    if gene:
      conditions.append('gene_map = \'%s\'' % gene)
    if min_mut:
      having_conditions.append('SUM(num_mutations) > %s' % min_mut)
    if max_mut:
      having_conditions.append('SUM(num_mutations) < %s' % max_mut)

    cond_line = ""
    if len(conditions) == 0:
      pass
    elif len(conditions) == 1:
      cond_line += ' WHERE ' + conditions[0]
    else:
      cond_line = ' WHERE ' + (' AND ').join(conditions)

    sql_query += cond_line
    sql_query += ' GROUP BY pdom_id'

    having_query = ""
    if len(having_conditions) == 0:
      pass
    elif len(having_conditions) == 1:
      having_query += ' HAVING ' + having_conditions[0]
    else:
      having_query += ' HAVING ' + (' AND ').join(having_conditions)

    sql_query += having_query

    print sql_query
    cursor = g.conn.execute(sql_query)

    for result in cursor:
      pdom_results.append((result['pdom_id'], result['total_mutations']))  
    cursor.close()

  return render_template("another.html", pdoms = pdom_results)

@app.route('/search_cd', methods=["POST", "GET"])
def search_comments():
  gene = request.form['gene']

  error = 0
  if len(gene) > 8:
    error = 1
  
  comment_results = []
  if not error:
    sql_query = 'SELECT l.gene_name, l.pdom_id, d.topic, mo.uid, c.com_text, m.uid, m.com_timestamp \
    FROM comment_in ci JOIN comment c ON c.cid = ci.cid JOIN discussion_page d ON d.did = ci.did JOIN linked l ON l.did = d.did \
    JOIN makes_comment m ON m.cid = c.cid JOIN moderator_of mo ON mo.did = l.did \
    WHERE l.gene_name = \'%s\';' % gene
    print sql_query

    cursor = g.conn.execute(sql_query)

    for result in cursor:
      comment_results.append((result['gene_name'], result['pdom_id'], result['topic'], result[3], result['com_text'], result[5], result['com_timestamp']))  
    cursor.close()

    print comment_results

  return render_template("another.html", comment_results = comment_results)

# Example of adding new data to the database
@app.route('/add', methods=['POST'])
def add():
  # Get input from user_input
  new_gene = request.form['gene']
  new_pdom = request.form['pdom']
  loc = request.form['location']
  new_mutations = request.form['num_of_mutations']

  error = 0
  if not new_gene or not new_pdom or not loc or not new_mutations: # Missing Data
    error = 1
  if len(new_gene) > 8 or len(new_pdom) > 8 or len(loc) > 8 or len(new_mutations) > 8:
    error = 1
  if not all(char.isdigit() for char in loc) and not all(char.isdigit() for char in new_mutations):
    error = 1

  if not error:
    select_sql = "SELECT * FROM gene_page WHERE gene_name = '%s' AND pdom_id = '%s';"
    cursor = g.conn.execute(select_sql % (new_gene, new_pdom))
    data = cursor.fetchall()
    cursor.close()

    select_sql = "SELECT * FROM protein_dom_pg WHERE gene_map = \'%s\' AND pdom_id = \'%s\';"
    cursor = g.conn.execute(select_sql % (new_gene, new_pdom))
    p_data = cursor.fetchall()
    cursor.close()

    add_gene = ""
    add_pdom = "" 
    if len(data) == 0: # If the entry is of a new value
      add_gene = "INSERT INTO gene_page VALUES (\'%s\', \'%s\', %s, %s)" % (new_gene, new_pdom, loc, new_mutations)
      add_pdom = "INSERT INTO protein_dom_pg VALUES (\'%s\', \'%s\', %s)" % (new_pdom, new_gene, new_mutations)

    else: # entry exists - updating
      if len(p_data) == 0:
        add_pdom = "INSERT INTO protein_dom_pg VALUES (\'%s\', \'%s\', %s)" % (new_pdom, new_gene, new_mutations)
      else:
        add_pdom = "UPDATE protein_dom_pg SET num_mutations = num_mutations + %s WHERE gene_map = \'%s\' AND pdom_id = \'%s\';" % (new_mutations, new_gene, new_pdom)
      add_gene = "UPDATE gene_page SET num_mutations = num_mutations + %s WHERE gene_name = \'%s\' AND pdom_id = \'%s\';" % (new_mutations, new_gene, new_pdom)

    print add_gene
    print add_pdom

    g.conn.execute(add_gene)
    g.conn.execute(add_pdom)

  return redirect('/')

@app.route('/login')
def login():
    abort(401)
    this_is_never_executed()

if __name__ == "__main__":
  import click

  @click.command()
  @click.option('--debug', is_flag=True)
  @click.option('--threaded', is_flag=True)
  @click.argument('HOST', default='0.0.0.0')
  @click.argument('PORT', default=8111, type=int)
  def run(debug, threaded, host, port):

    HOST, PORT = host, port
    print "running on %s:%d" % (HOST, PORT)
    app.run(host=HOST, port=PORT, debug=debug, threaded=threaded)


  run()
