// World-frame spatial velocities; q = xyz,wxyz,hinges; v = linear,angular,hinges.
#include <Eigen/Dense>
#include <btBulletCollisionCommon.h>
#include <memory>
#include <chrono>
#include <Eigen/Geometry>
#include <vector>
#include <string>
#include <stdexcept>
#include <cmath>
#include <algorithm>
using namespace Eigen;
using V3=Vector3d; using M3=Matrix3d;
static M3 skew(const V3& v){M3 s;s<<0,-v.z(),v.y(),v.z(),0,-v.x(),-v.y(),v.x(),0;return s;}
static Quaterniond quat(const double* a){Quaterniond q(a[0],a[1],a[2],a[3]);if(q.norm()<1e-12)throw std::runtime_error("Zero quaternion");return q.normalized();}
struct Body {int parent,joint; double mass,damping,friction,armature,lo,hi,effort; V3 offset,axis,com,p,w,alpha,acc,origin,axisWorld; M3 rotation,rest,inertia; MatrixXd jv,jw;};
struct Shape {int body; std::vector<V3> points; double radius,mu; bool cylinder=false; V3 center=V3::Zero(), axis=V3::UnitZ(); double half=0;};
struct Contact {int body,other=-1; M3 frame=M3::Identity(),effective=M3::Zero(); V3 point; double depth,normal=0,tx=0,ty=0,mu; MatrixXd j; MatrixXd response;};
struct World {
 double dt,time=0,maxDepth=0,residual=0; int nj=0,iterations=60; V3 gravity=V3(0,0,-9.81); bool ground=true;
 std::vector<Body> bodies; std::vector<Shape> shapes; std::vector<Contact> contacts;
 VectorXd q,v,tau,external; MatrixXd mass; LDLT<MatrixXd> factor;
 std::unique_ptr<btDefaultCollisionConfiguration> collisionConfig;
 std::unique_ptr<btCollisionDispatcher> dispatcher;
 std::unique_ptr<btDbvtBroadphase> broadphase;
 std::unique_ptr<btCollisionWorld> collisionWorld;
 std::vector<std::unique_ptr<btCollisionShape>> collisionShapes;
 std::vector<std::unique_ptr<btCollisionObject>> collisionObjects;
 bool bodyContacts=false,fixedBase=false;
 double profile[4]={0,0,0,0};
 bool excluded(int a,int b)const{return (a<0&&b<0)||(a>=0&&b>=0&&(a==b||bodies[a].parent==b||bodies[b].parent==a));}
 ~World(){if(collisionWorld)for(auto& o:collisionObjects)collisionWorld->removeCollisionObject(o.get());}
 explicit World(double step):dt(step){if(!std::isfinite(dt)||dt<=0)throw std::runtime_error("Invalid timestep");}
 int dofs()const{return 6+nj;}
 void initialize(){q=VectorXd::Zero(7+nj);q[3]=1;v=VectorXd::Zero(dofs());tau=VectorXd::Zero(nj);external=VectorXd::Zero(dofs());}
 void kinematics(){
  int n=dofs(); M3 base=quat(q.data()+3).toRotationMatrix();
  for(auto& b:bodies){
   b.jv=MatrixXd::Zero(3,n);b.jw=MatrixXd::Zero(3,n);
   if(b.parent<0){b.p=q.head<3>();b.rotation=base;b.w=v.segment<3>(3);b.alpha.setZero();b.acc.setZero();b.jv.block<3,3>(0,0).setIdentity();b.jw.block<3,3>(0,3).setIdentity();}
   else {auto& a=bodies[b.parent];V3 r=a.rotation*b.offset;b.p=a.p+r;b.origin=b.p;
    b.rotation=a.rotation*b.rest;b.axisWorld=b.rotation*b.axis;
    b.jv=a.jv-skew(r)*a.jw;b.jw=a.jw;b.w=a.w;b.alpha=a.alpha;
    b.acc=a.acc+a.alpha.cross(r)+a.w.cross(a.w.cross(r));
    if(b.joint>=0){int k=6+b.joint;V3 omega=b.axisWorld*v[k];b.w+=omega;b.alpha+=a.w.cross(omega);b.jw.col(k)+=b.axisWorld;b.rotation*=AngleAxisd(q[7+b.joint],b.axis).toRotationMatrix();}
   }
  }
 }
 MatrixXd jac(int id,const V3& local){auto& b=bodies.at(id);return b.jv-skew(b.rotation*local)*b.jw;}
 void dynamics(){
  int n=dofs();mass=MatrixXd::Zero(n,n);VectorXd bias=VectorXd::Zero(n);
  for(auto& b:bodies){V3 r=b.rotation*b.com;MatrixXd j=b.jv-skew(r)*b.jw;M3 inertia=b.rotation*b.inertia*b.rotation.transpose();
   mass.noalias()+=b.mass*j.transpose()*j+b.jw.transpose()*inertia*b.jw;
   V3 a=b.acc+b.alpha.cross(r)+b.w.cross(b.w.cross(r));
   bias.noalias()+=j.transpose()*(b.mass*(a-gravity))+b.jw.transpose()*(inertia*b.alpha+b.w.cross(inertia*b.w));
   if(b.joint>=0){int k=6+b.joint;mass(k,k)+=b.armature;bias[k]+=b.damping*v[k]+b.friction*std::clamp(v[k]/0.001,-1.,1.);}
  }
  factor.compute(mass);if(factor.info()!=Success||!factor.isPositive()||factor.vectorD().minCoeff()<1e-12)throw std::runtime_error("Singular or indefinite mass matrix");
  VectorXd force=external-bias;
  for(auto& b:bodies)if(b.joint>=0)force[6+b.joint]+=std::clamp(tau[b.joint],-b.effort,b.effort);
  v+=dt*factor.solve(force);
 }
 void buildCollisionWorld(){
  if(collisionWorld)return;
  collisionConfig=std::make_unique<btDefaultCollisionConfiguration>();
  dispatcher=std::make_unique<btCollisionDispatcher>(collisionConfig.get());
  broadphase=std::make_unique<btDbvtBroadphase>();
  collisionWorld=std::make_unique<btCollisionWorld>(dispatcher.get(),broadphase.get(),collisionConfig.get());
  for(auto& s:shapes){
   std::unique_ptr<btCollisionShape> shape;
   if(s.cylinder){shape=std::make_unique<btCylinderShapeZ>(btVector3(s.radius,s.radius,s.half));shape->setMargin(0);}
   else if(s.radius>0){if(s.points.size()!=1)throw std::runtime_error("Sphere collider requires one center");shape=std::make_unique<btSphereShape>(s.radius);}
   else{auto hull=std::make_unique<btConvexHullShape>();for(auto& p:s.points)hull->addPoint(btVector3(p.x(),p.y(),p.z()),false);hull->optimizeConvexHull();hull->recalcLocalAabb();hull->setMargin(0);
    s.points.clear();for(int i=0;i<hull->getNumPoints();i++){const auto& p=hull->getUnscaledPoints()[i];s.points.emplace_back(p.x(),p.y(),p.z());}
    shape=std::move(hull);}
   auto object=std::make_unique<btCollisionObject>();object->setCollisionShape(shape.get());object->setUserIndex(s.body);object->setUserIndex2(int(collisionObjects.size()));object->setCollisionFlags(s.body<0?btCollisionObject::CF_STATIC_OBJECT:0);
   collisionWorld->addCollisionObject(object.get());collisionShapes.push_back(std::move(shape));collisionObjects.push_back(std::move(object));
  }
  for(size_t i=0;i<collisionObjects.size();i++)for(size_t j=0;j<i;j++){
   int a=shapes[i].body,b=shapes[j].body;
   if(excluded(a,b)){collisionObjects[i]->setIgnoreCollisionCheck(collisionObjects[j].get(),true);collisionObjects[j]->setIgnoreCollisionCheck(collisionObjects[i].get(),true);}
  }
 }
 void collideBodies(){
  buildCollisionWorld();
  for(size_t i=0;i<shapes.size();i++){auto& s=shapes[i];V3 p=V3::Zero();M3 r=M3::Identity();if(s.body>=0){p=bodies[s.body].p;r=bodies[s.body].rotation;}
   if(s.cylinder){p+=r*s.center;V3 z=V3::UnitZ(),cross=z.cross(s.axis);double cosine=z.dot(s.axis);Quaterniond align;
    if(cosine< -0.999999)align=Quaterniond(0,1,0,0);else align=Quaterniond(1+cosine,cross.x(),cross.y(),cross.z()).normalized();r*=align.toRotationMatrix();}
   else if(s.radius>0)p+=r*s.points[0];
   Quaterniond q(r);btTransform transform(btQuaternion(q.x(),q.y(),q.z(),q.w()),btVector3(p.x(),p.y(),p.z()));collisionObjects[i]->setWorldTransform(transform);
  }
  collisionWorld->performDiscreteCollisionDetection();
  for(int i=0;i<dispatcher->getNumManifolds();i++){auto* manifold=dispatcher->getManifoldByIndexInternal(i);auto* oa=manifold->getBody0();auto* ob=manifold->getBody1();int a=oa->getUserIndex(),b=ob->getUserIndex();
   if(excluded(a,b))continue;
   for(int j=0;j<manifold->getNumContacts();j++){auto& p=manifold->getContactPoint(j);if(p.getDistance()>0)continue;
    auto va=p.getPositionWorldOnA(),vb=p.getPositionWorldOnB(),vn=p.m_normalWorldOnB;
    V3 pa(va.x(),va.y(),va.z()),pb(vb.x(),vb.y(),vb.z()),n(vn.x(),vn.y(),vn.z());n.normalize();
    Contact c;c.body=a;c.other=b;c.point=(pa+pb)*.5;c.depth=-p.getDistance();c.mu=std::max(shapes[oa->getUserIndex2()].mu,shapes[ob->getUserIndex2()].mu);
    c.frame.col(2)=n;c.frame.col(0)=n.unitOrthogonal();c.frame.col(1)=n.cross(c.frame.col(0));
    MatrixXd ja=MatrixXd::Zero(3,dofs()),jb=MatrixXd::Zero(3,dofs());
    if(a>=0)ja=jac(a,bodies[a].rotation.transpose()*(pa-bodies[a].p));
    if(b>=0)jb=jac(b,bodies[b].rotation.transpose()*(pb-bodies[b].p));
    c.j=c.frame.transpose()*(ja-jb);
    c.response=factor.solve(c.j.transpose());c.effective=c.j*c.response;maxDepth=std::max(maxDepth,c.depth);contacts.push_back(c);
   }
  }
 }
 void collide(){contacts.clear();maxDepth=0;
  if(bodyContacts)collideBodies();
  if(!ground)return;
  for(auto& s:shapes){if(s.body<0)continue;auto& b=bodies[s.body];std::vector<std::pair<double,V3>> candidates;
   std::vector<V3> support=s.points;
   if(s.cylinder){
    V3 a=b.rotation*s.axis;V3 down(0,0,-1);V3 radial=down-a*down.dot(a);
    double norm=radial.norm();support.clear();
    if(norm<1e-9){V3 u=a.unitOrthogonal(),t=a.cross(u);double sign=a.z()>0?-1.:1.;
     for(const V3& r:std::vector<V3>{u,-u,t,-t})support.push_back(s.center+b.rotation.transpose()*(sign*s.half*a+s.radius*r));
    }else{radial*=s.radius/norm;
     if(std::abs(a.z())<1e-9){support.push_back(s.center+b.rotation.transpose()*(s.half*a+radial));support.push_back(s.center+b.rotation.transpose()*(-s.half*a+radial));}
     else support.push_back(s.center+b.rotation.transpose()*((a.z()>0?-1.:1.)*s.half*a+radial));
    }
   }
   for(auto& p:support){V3 x=b.p+b.rotation*p;double sphereRadius=s.cylinder?0:s.radius;double gap=x.z()-sphereRadius;if(gap<0.002){V3 local=p-b.rotation.transpose()*V3(0,0,sphereRadius);candidates.emplace_back(gap,local);}}
   std::sort(candidates.begin(),candidates.end(),[](const auto& a,const auto& b){return a.first<b.first;});
   int count=0;for(auto& p:candidates){if(count++==4)break;Contact c;c.body=s.body;c.point=b.p+b.rotation*p.second;c.depth=-p.first;c.mu=s.mu;c.j=jac(s.body,p.second);c.response=factor.solve(c.j.transpose());c.effective=c.j*c.response;maxDepth=std::max(maxDepth,c.depth);contacts.push_back(c);}
  }
 }
 void solve(){
  MatrixXd baseResponse;Matrix<double,6,6> baseInverse;
  if(fixedBase){baseResponse=factor.solve(MatrixXd::Identity(dofs(),6));baseInverse=baseResponse.topRows(6).inverse();}
  for(int iter=0;iter<iterations;iter++){double change=0;
   for(auto& b:bodies)if(b.joint>=0){int k=6+b.joint;double angle=q[7+b.joint];double lower=(b.lo-angle)/dt,upper=(b.hi-angle)/dt;
    if(v[k]<lower||v[k]>upper){VectorXd e=VectorXd::Zero(dofs());e[k]=1;VectorXd response=factor.solve(e);double target=std::clamp(v[k],lower,upper);change=std::max(change,std::abs(target-v[k]));v+=response*((target-v[k])/response[k]);}}
   for(auto& c:contacts){const M3& eff=c.effective;if(eff(2,2)<1e-12)continue;double target=std::clamp(0.2*std::max(c.depth-0.0001,0.)/dt,0.,2.);if(c.depth<0)target=c.depth/dt;
    double old=c.normal;c.normal=std::max(0.,old+(target-(c.j*v).z())/eff(2,2));change=std::max(change,std::abs(c.normal-old));v+=c.response.col(2)*(c.normal-old);
    Vector2d oldt(c.tx,c.ty),t=oldt;Vector3d cv=c.j*v;
    t.x()-=cv.x()/std::max(eff(0,0),1e-12);t.y()-=cv.y()/std::max(eff(1,1),1e-12);double bound=c.mu*c.normal;if(t.norm()>bound)t*=bound/t.norm();
    change=std::max(change,(t-oldt).norm());v+=c.response.leftCols(2)*(t-oldt);c.tx=t.x();c.ty=t.y();
   }
   if(fixedBase){change=std::max(change,v.head(6).norm());VectorXd correction=baseInverse*(-v.head(6));v+=baseResponse*correction;}
   if(iter>=1&&change<1e-9)break;
  }
  residual=0;for(auto& c:contacts){double target=c.depth<0?c.depth/dt:std::clamp(0.2*std::max(c.depth-0.0001,0.)/dt,0.,2.);double r=(c.j*v).z()-target;residual=std::max(residual,c.normal>1e-9?std::abs(r):std::max(0.,-r));}
 }
 void step(){
  using Clock=std::chrono::steady_clock;auto t=Clock::now();
  kinematics();auto t1=Clock::now();dynamics();auto t2=Clock::now();collide();auto t3=Clock::now();solve();auto t4=Clock::now();
  profile[0]+=std::chrono::duration<double>(t1-t).count();profile[1]+=std::chrono::duration<double>(t2-t1).count();profile[2]+=std::chrono::duration<double>(t3-t2).count();profile[3]+=std::chrono::duration<double>(t4-t3).count();q.head<3>()+=dt*v.head<3>();
  Quaterniond rotation=quat(q.data()+3);V3 w=v.segment<3>(3);double a=w.norm()*dt;if(a>0)rotation=Quaterniond(AngleAxisd(a,w.normalized()))*rotation;rotation.normalize();q.segment<4>(3)<<rotation.w(),rotation.x(),rotation.y(),rotation.z();q.tail(nj)+=dt*v.tail(nj);time+=dt;
  if(!q.allFinite()||!v.allFinite())throw std::runtime_error("Non-finite physics state");
  external.setZero();kinematics();
 }
};
static thread_local std::string error;
template<class F>int guard(F f){try{f();error.clear();return 0;}catch(const std::exception& e){error=e.what();return -1;}}
extern "C" {
const char* ms_error(){return error.c_str();}
void* ms_create(double dt){try{return new World(dt);}catch(const std::exception& e){error=e.what();return nullptr;}}
void ms_destroy(World* w){delete w;}
// params: mass, offset3, rest quaternion4, com3, inertia9, axis3, damping, friction,
// armature, lower, upper, effort. Bodies must be added in parent-first order.
int ms_body(World* w,int parent,int hinge,const double* p){return guard([&]{if(parent>=int(w->bodies.size())||parent< -1||(parent<0&&!w->bodies.empty()))throw std::runtime_error("Invalid body tree");Body b{};b.p.setZero();b.w.setZero();b.alpha.setZero();b.acc.setZero();b.origin.setZero();b.axisWorld.setZero();b.rotation.setIdentity();b.parent=parent;b.joint=hinge?w->nj++:-1;b.mass=p[0];b.offset=Map<const V3>(p+1);b.rest=quat(p+4).toRotationMatrix();b.com=Map<const V3>(p+8);b.inertia=Map<const Matrix<double,3,3,RowMajor>>(p+11);b.axis=Map<const V3>(p+20).normalized();b.damping=p[23];b.friction=p[24];b.armature=p[25];b.lo=p[26];b.hi=p[27];b.effort=p[28];if(b.mass<=0||!b.inertia.allFinite()||b.lo>b.hi)throw std::runtime_error("Invalid body parameters");w->bodies.push_back(b);});}
int ms_init(World* w){return guard([&]{if(w->bodies.empty())throw std::runtime_error("No bodies");w->initialize();});}
int ms_shape(World* w,int body,int count,const double* points,double radius,double mu){return guard([&]{if(body< -1||body>=int(w->bodies.size())||count<=0||radius<0||mu<0)throw std::runtime_error("Invalid collider");Shape s;s.body=body;s.radius=radius;s.mu=mu;for(int i=0;i<count;i++)s.points.emplace_back(Map<const V3>(points+3*i));w->shapes.push_back(s);});}
int ms_cylinder(World* w,int body,const double* center,const double* axis,double radius,double half,double mu){return guard([&]{if(body< -1||body>=int(w->bodies.size())||radius<=0||half<=0||mu<0)throw std::runtime_error("Invalid cylinder");Shape s;s.body=body;s.cylinder=true;s.center=Map<const V3>(center);s.axis=Map<const V3>(axis).normalized();s.radius=radius;s.half=half;s.mu=mu;w->shapes.push_back(s);});}
int ms_set(World* w,const double* q,const double* v){return guard([&]{w->q=Map<const VectorXd>(q,7+w->nj);w->v=Map<const VectorXd>(v,w->dofs());if(!w->q.allFinite()||!w->v.allFinite())throw std::runtime_error("Invalid state");quat(w->q.data()+3);w->kinematics();});}
int ms_get(World* w,double* q,double* v){return guard([&]{Map<VectorXd>(q,7+w->nj)=w->q;Map<VectorXd>(v,w->dofs())=w->v;});}
int ms_step(World* w,const double* tau,int count){return guard([&]{if(count<1)throw std::runtime_error("Invalid step count");w->tau=Map<const VectorXd>(tau,w->nj);if(!w->tau.allFinite())throw std::runtime_error("Invalid moments");for(int i=0;i<count;i++)w->step();});}
int ms_pose(World* w,int id,double* out){return guard([&]{auto& b=w->bodies.at(id);Map<V3> position(out);position=b.p;Quaterniond r(b.rotation);out[3]=r.w();out[4]=r.x();out[5]=r.y();out[6]=r.z();});}
int ms_jac(World* w,int id,const double* point,double* out){return guard([&]{w->kinematics();Map<Matrix<double,3,Dynamic,RowMajor>>(out,3,w->dofs())=w->jac(id,Map<const V3>(point));});}
int ms_force(World* w,int id,const double* point,const double* force,const double* torque){return guard([&]{w->kinematics();w->external+=w->jac(id,Map<const V3>(point)).transpose()*Map<const V3>(force)+w->bodies.at(id).jw.transpose()*Map<const V3>(torque);});}
int ms_fixed_base(World* w,int enabled){return guard([&]{w->fixedBase=enabled;});}
int ms_body_contacts(World* w,int enabled){return guard([&]{w->bodyContacts=enabled;});}
int ms_options(World* w,const double* g,int ground,int iterations){return guard([&]{w->gravity=Map<const V3>(g);w->ground=ground;w->iterations=iterations;});}
int ms_contacts(World* w,double* out,int capacity){int n=std::min(capacity,int(w->contacts.size()));for(int i=0;i<n;i++){auto& c=w->contacts[i];double* p=out+i*13;p[0]=c.body;Map<V3>(p+1)=c.point;p[4]=c.depth;p[5]=c.normal;p[6]=c.tx;p[7]=c.ty;p[8]=c.mu;p[9]=c.other;Map<V3>(p+10)=c.frame.col(2);}return int(w->contacts.size());}
int ms_energy(World* w,double* out){return guard([&]{w->kinematics();double kinetic=0,potential=0;
 for(auto& b:w->bodies){V3 r=b.rotation*b.com;V3 linear=(b.jv-skew(r)*b.jw)*w->v;V3 angular=b.jw*w->v;M3 inertia=b.rotation*b.inertia*b.rotation.transpose();kinetic+=.5*b.mass*linear.squaredNorm()+.5*angular.dot(inertia*angular);potential-=b.mass*w->gravity.dot(b.p+r);if(b.joint>=0)kinetic+=.5*b.armature*w->v[6+b.joint]*w->v[6+b.joint];}out[0]=kinetic;out[1]=potential;});}
void ms_diagnostics(World* w,double* out){out[0]=w->time;out[1]=w->maxDepth;out[2]=w->residual;}
void ms_profile(World* w,double* out){for(int i=0;i<4;i++)out[i]=w->profile[i];}
int ms_reset(World* w){return guard([&]{w->time=0;for(double& p:w->profile)p=0;w->external.setZero();w->tau.setZero();w->contacts.clear();w->maxDepth=w->residual=0;});}
}
